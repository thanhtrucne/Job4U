"""Jobs API routes."""
import logging
from typing import Optional
from math import ceil
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models import Job, Company, JobSkill
from backend.schemas import PaginatedJobs, JobList, JobOut
from backend.services.job_service import get_jobs, get_job_by_id
from backend.services import recommendation_service
from backend.config import settings

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)


def _job_to_list(job: Job) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "company_name": job.company.name if job.company else None,
        "company_logo": job.company.logo_url if job.company else None,
        "salary": job.salary,
        "location": job.location,
        "experience": job.experience,
        "job_level": job.job_level,
        "deadline": job.deadline,
        "job_type": job.job_type,
        "job_url": job.job_url,
        "created_at": job.created_at,
        "created_time": job.created_time,
    }


@router.get("", response_model=PaginatedJobs)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    location: Optional[str] = None,
    company: Optional[str] = None,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    total, jobs = await get_jobs(db, page, page_size, location, company, category, keyword)
    total_pages = ceil(total / page_size) if page_size else 1
    return PaginatedJobs(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        jobs=[JobList(**_job_to_list(j)) for j in jobs],
    )


@router.get("/latest")
async def latest_jobs(
    limit: int = Query(6, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import desc
    result = await db.execute(
        select(Job)
        .where(Job.is_active == True)
        .options(selectinload(Job.company))
        .order_by(desc(Job.created_at))
        .limit(limit)
    )
    jobs = result.scalars().all()
    return [_job_to_list(j) for j in jobs]


@router.get("/recommend/{job_id}", summary="Goi y viec lam tuong tu")
async def get_recommendations(
    job_id: int,
    top_n: int = Query(5, ge=1, le=20, description="So luong job goi y (1-20)"),
    db: AsyncSession = Depends(get_db),
):
    """
    **Job Recommendation API** - Su dung Content-Based Filtering

    Thuat toan:
    - Ket hop title + description + requirements + skills thanh van ban
    - Chuyen van ban thanh vector bang **TF-IDF Vectorizer**
    - Tinh **Cosine Similarity** giua job hien tai va tat ca cac job khac
    - Tra ve `top_n` job co do tuong dong cao nhat

    Returns:
        List[dict]: Danh sach job goi y, moi job co `similarity_score` [0..1]
    """
    try:
        recommendations = await recommendation_service.recommend_jobs(
            job_id=job_id, db=db, top_n=top_n
        )
        return {
            "job_id": job_id,
            "total": len(recommendations),
            "recommendations": recommendations,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"[Recommendation] Loi khi goi y cho job_id={job_id}: {e}")
        raise HTTPException(status_code=500, detail="Loi he thong recommendation.")


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await get_job_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    data = {
        "id": job.id,
        "title": job.title,
        "salary": job.salary,
        "location": job.location,
        "experience": job.experience,
        "job_level": job.job_level,
        "description": job.description,
        "requirements": job.requirements,
        "benefits": job.benefits,
        "job_url": job.job_url,
        "deadline": job.deadline,
        "job_type": job.job_type,
        "created_time": job.created_time,
        "is_active": job.is_active,
        "created_at": job.created_at,
        "company": job.company,
        "category": job.category,
        "skills": [js.skill for js in job.job_skills],
    }
    return JobOut(**data)
