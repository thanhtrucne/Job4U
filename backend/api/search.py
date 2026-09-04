"""Search API routes."""
import logging
from typing import Optional
from math import ceil
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas import PaginatedJobs, JobList
from backend.services.search_service import full_text_search
from backend.config import settings

router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger(__name__)


def _job_to_list(job) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "company_name": job.company.name if job.company else None,
        "company_logo": job.company.logo_url if job.company else None,
        "salary": job.salary,
        "location": job.location,
        "experience": job.experience,
        "deadline": job.deadline,
        "job_type": job.job_type,
        "job_url": job.job_url,
        "created_at": job.created_at,
        "created_time": job.created_time,
    }


@router.get("", response_model=PaginatedJobs)
async def search_jobs(
    request: Request,
    keyword: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    skill: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    total, jobs = await full_text_search(
        db,
        keyword=keyword,
        location=location,
        category=category,
        company=company,
        skill=skill,
        page=page,
        page_size=page_size,
        request_ip=ip,
    )
    total_pages = ceil(total / page_size) if page_size else 1
    return PaginatedJobs(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        jobs=[JobList(**_job_to_list(j)) for j in jobs],
    )
