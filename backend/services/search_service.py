"""Full-text and filtered search service using PostgreSQL."""
import logging
from typing import Tuple, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, desc
from sqlalchemy.orm import selectinload

from backend.models import Job, Company, Category, JobSkill, SearchLog

logger = logging.getLogger(__name__)


async def full_text_search(
    db: AsyncSession,
    keyword: Optional[str] = None,
    location: Optional[str] = None,
    category: Optional[str] = None,
    company: Optional[str] = None,
    skill: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    request_ip: Optional[str] = None,
) -> Tuple[int, List[Job]]:
    q = select(Job).where(Job.is_active == True).options(selectinload(Job.company))

    if keyword:
        from sqlalchemy import or_
        # Use regex with word boundaries (\y in Postgres) for precise matching
        # while keeping FTS for broader context support
        q = q.where(
            or_(
                Job.title.op("~*")(f"\\y{keyword}\\y"),
                Job.keywords.op("~*")(f"\\y{keyword}\\y"),
                Job.search_vector.op("@@")(func.plainto_tsquery("english", keyword))
            )
        )
    if location:
        q = q.where(Job.location.ilike(f"%{location}%"))
    if company:
        q = q.join(Company, isouter=True).where(Company.name.ilike(f"%{company}%"))
    if category:
        q = q.join(Category, isouter=True).where(Category.name.ilike(f"%{category}%"))
    if skill:
        from backend.models import Skill
        skill_sub = (
            select(JobSkill.job_id)
            .join(Skill)
            .where(Skill.name.ilike(f"%{skill}%"))
            .subquery()
        )
        q = q.where(Job.id.in_(skill_sub))

    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar() or 0

    if keyword:
        rank = func.ts_rank(Job.search_vector, func.plainto_tsquery("english", keyword))
        q = q.order_by(desc(rank), desc(Job.created_at))
    else:
        q = q.order_by(desc(Job.created_at))

    q = q.offset((page - 1) * page_size).limit(page_size)
    jobs = (await db.execute(q)).scalars().all()

    # Log search
    try:
        log = SearchLog(
            keyword=keyword,
            location=location,
            category=category,
            results_count=total,
            ip_address=request_ip,
        )
        db.add(log)
        await db.commit()
    except Exception:
        pass

    return total, jobs
