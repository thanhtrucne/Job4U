"""Companies API routes."""
from typing import Optional
from math import ceil
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models import Company, Job
from backend.schemas import CompanyOut, CompanyWithJobs

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("")
async def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    total_q = select(func.count()).select_from(Company)
    total = (await db.execute(total_q)).scalar() or 0

    result = await db.execute(
        select(Company)
        .order_by(Company.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    companies = result.scalars().all()

    items = []
    for c in companies:
        cnt_result = await db.execute(
            select(func.count()).select_from(Job).where(Job.company_id == c.id, Job.is_active == True)
        )
        cnt = cnt_result.scalar() or 0
        items.append({**CompanyOut.model_validate(c).model_dump(), "job_count": cnt})

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": ceil(total / page_size) if page_size else 1,
        "companies": items,
    }


@router.get("/top")
async def top_companies(limit: int = Query(6, ge=1, le=20), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Company.id, Company.name, Company.logo_url, Company.industry, Company.location,
               func.count(Job.id).label("job_count"))
        .join(Job, Job.company_id == Company.id, isouter=True)
        .where(Job.is_active == True)
        .group_by(Company.id)
        .order_by(desc("job_count"))
        .limit(limit)
    )
    rows = result.all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "logo_url": r.logo_url,
            "industry": r.industry,
            "location": r.location,
            "job_count": r.job_count,
        }
        for r in rows
    ]


@router.get("/{company_id}")
async def get_company(company_id: int, db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    cnt = (await db.execute(
        select(func.count()).select_from(Job).where(Job.company_id == company_id, Job.is_active == True)
    )).scalar() or 0

    return {**CompanyOut.model_validate(company).model_dump(), "job_count": cnt}
