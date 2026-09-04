"""Service layer for job CRUD and business logic."""
import logging
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, text, desc
from sqlalchemy.orm import selectinload

from backend.models import Job, Company, Category, Skill, JobSkill
from backend.schemas import JobCreate, JobList
from backend.websocket.ws_manager import manager

logger = logging.getLogger(__name__)


def _to_slug(name: str) -> str:
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    return slug


async def get_or_create_company(db: AsyncSession, name: str) -> Company:
    result = await db.execute(select(Company).where(Company.name == name))
    company = result.scalars().first()
    if not company:
        company = Company(name=name, slug=_to_slug(name))
        db.add(company)
        await db.flush()
    return company


async def get_or_create_category(db: AsyncSession, name: str) -> Category:
    result = await db.execute(select(Category).where(Category.name == name))
    cat = result.scalars().first()
    if not cat:
        cat = Category(name=name, slug=_to_slug(name))
        db.add(cat)
        await db.flush()
    return cat


async def get_or_create_skill(db: AsyncSession, name: str) -> Skill:
    result = await db.execute(select(Skill).where(Skill.name == name))
    skill = result.scalars().first()
    if not skill:
        skill = Skill(name=name)
        db.add(skill)
        await db.flush()
    return skill


async def create_job(db: AsyncSession, job_data: JobCreate) -> Optional[Job]:
    """Insert a job; returns None if URL already exists."""
    result = await db.execute(select(Job).where(Job.job_url == job_data.job_url))
    if result.scalars().first():
        return None

    company = None
    if job_data.company_name:
        company = await get_or_create_company(db, job_data.company_name)

    category = None
    if job_data.category_name:
        category = await get_or_create_category(db, job_data.category_name)

    job = Job(
        title=job_data.title,
        company_id=company.id if company else None,
        category_id=category.id if category else None,
        salary=job_data.salary,
        location=job_data.location,
        experience=job_data.experience,
        job_level=job_data.job_level,
        description=job_data.description,
        requirements=job_data.requirements,
        benefits=job_data.benefits,
        job_url=job_data.job_url,
        deadline=job_data.deadline,
        job_type=job_data.job_type,
        created_time=job_data.created_time,
    )
    db.add(job)
    await db.flush()

    # skills
    for skill_name in job_data.skills:
        skill_name = skill_name.strip()
        if skill_name:
            skill = await get_or_create_skill(db, skill_name)
            js = JobSkill(job_id=job.id, skill_id=skill.id)
            db.add(js)

    await db.flush()

    # Update FTS vector
    await db.execute(
        text("""
            UPDATE jobs SET search_vector =
                to_tsvector('english',
                    coalesce(title,'') || ' ' ||
                    coalesce(description,'') || ' ' ||
                    coalesce(location,'')
                )
            WHERE id = :id
        """),
        {"id": job.id},
    )

    await db.commit()

    # Broadcast via WebSocket
    await manager.send_new_job({
        "id": job.id,
        "title": job.title,
        "company": company.name if company else None,
        "location": job.location,
        "salary": job.salary,
        "job_url": job.job_url,
    })

    return job


async def get_jobs(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    location: Optional[str] = None,
    company: Optional[str] = None,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
) -> Tuple[int, List[Job]]:

    base_query = select(Job).where(Job.is_active == True)

    if keyword:
        base_query = base_query.where(
            or_(
                Job.title.op("~*")(f"\\y{keyword}\\y"),
                Job.keywords.op("~*")(f"\\y{keyword}\\y")
            )
        )

    if location:
        base_query = base_query.where(Job.location.ilike(f"%{location}%"))

    if company:
        base_query = base_query.join(Company).where(
            Company.name.ilike(f"%{company}%")
        )

    if category:
        base_query = base_query.join(Category).where(
            Category.name.ilike(f"%{category}%")
        )

    # total
    total = (
        await db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
    ).scalar() or 0

    # jobs
    jobs_query = (
        base_query
        .options(selectinload(Job.company))
        .order_by(desc(Job.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    jobs = (await db.execute(jobs_query)).scalars().all()

    return total, jobs


async def get_job_by_id(db: AsyncSession, job_id: int) -> Optional[Job]:
    result = await db.execute(
        select(Job)
        .where(Job.id == job_id)
        .options(
            selectinload(Job.company),
            selectinload(Job.category),
            selectinload(Job.job_skills).selectinload(JobSkill.skill),
        )
    )
    return result.scalars().first()
