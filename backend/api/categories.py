"""Categories API routes."""
from math import ceil
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from backend.database import get_db
from backend.models import Category, Job
from backend.schemas import CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
async def list_categories(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(select(func.count()).select_from(Category))).scalar() or 0
    result = await db.execute(
        select(Category)
        .order_by(Category.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    cats = result.scalars().all()

    items = []
    for c in cats:
        cnt = (await db.execute(
            select(func.count()).select_from(Job).where(Job.category_id == c.id, Job.is_active == True)
        )).scalar() or 0
        items.append({**CategoryOut.model_validate(c).model_dump(), "job_count": cnt})

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": ceil(total / page_size) if page_size else 1,
        "categories": items,
    }


@router.get("/top")
async def top_categories(limit: int = Query(8, ge=1, le=50), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Category.id, Category.name, Category.slug, func.count(Job.id).label("job_count"))
        .join(Job, Job.category_id == Category.id, isouter=True)
        .where(Job.is_active == True)
        .group_by(Category.id)
        .order_by(desc("job_count"))
        .limit(limit)
    )
    rows = result.all()
    return [{"id": r.id, "name": r.name, "slug": r.slug, "job_count": r.job_count} for r in rows]
