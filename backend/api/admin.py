"""Administrator-only management endpoints for users, jobs, and companies."""
from datetime import date
import re
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.auth import require_roles
from backend.database import get_db
from backend.models import Category, Company, Job, User

router = APIRouter(prefix="/admin", tags=["admin"])
JOB_LEVELS = {"Nhân viên", "Trưởng nhóm", "Trưởng / Phó phòng", "Quản lý / Giám sát", "Trưởng chi nhánh", "Phó giám đốc", "Giám đốc", "Thực tập sinh"}


class UserAdminUpdate(BaseModel):
    role: Literal["user", "partner", "admin"]
    is_active: bool
    company_id: Optional[int] = None


class JobAdminUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=2000)
    location: Optional[str] = None
    salary: Optional[str] = None
    experience: Optional[str] = None
    job_level: Optional[str] = None
    deadline: Optional[str] = None
    job_url: str = Field(min_length=1, max_length=4000)
    company_id: Optional[int] = None
    category_id: Optional[int] = None
    job_type: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    is_active: bool

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        try:
            selected_date = date.fromisoformat(value)
        except ValueError as error:
            raise ValueError("Hạn nộp hồ sơ phải có định dạng ngày hợp lệ.") from error
        if selected_date < date.today():
            raise ValueError("Hạn nộp hồ sơ không được ở trong quá khứ.")
        return value

    @field_validator("salary")
    @classmethod
    def validate_salary(cls, value: Optional[str]) -> Optional[str]:
        if not value or not re.search(r"\d", value):
            return value
        amounts = [int(item.replace(".", "").replace(",", "")) for item in re.findall(r"\d{1,3}(?:[.,]\d{3})+|\d+", value)]
        if re.search(r"triệu|\btr\b", value, re.IGNORECASE):
            amounts = [amount * 1_000_000 for amount in amounts]
        if any(amount < 1_000_000 for amount in amounts):
            raise ValueError("Mức lương phải từ 1.000.000 VNĐ trở lên.")
        if len(amounts) >= 2 and amounts[1] < amounts[0]:
            raise ValueError("Mức lương đến phải lớn hơn hoặc bằng mức lương từ.")
        return value


class CompanyAdminInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    website: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    is_partner: bool = False


def _user_item(item: User) -> dict:
    return {
        "id": item.id, "full_name": item.full_name, "email": item.email,
        "phone_number": item.phone_number, "role": item.role, "is_active": item.is_active,
        "company_id": item.company_id, "created_at": item.created_at,
    }


def _company_item(item: Company) -> dict:
    return {
        "id": item.id, "name": item.name, "website": item.website, "industry": item.industry,
        "size": item.size, "location": item.location, "description": item.description,
        "logo_url": item.logo_url, "is_partner": item.is_partner, "created_at": item.created_at,
    }


@router.get("/summary")
async def summary(_: User = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    jobs = (await db.execute(select(func.count()).select_from(Job))).scalar_one()
    active_jobs = (await db.execute(select(func.count()).select_from(Job).where(Job.is_active.is_(True)))).scalar_one()
    companies = (await db.execute(select(func.count()).select_from(Company))).scalar_one()
    return {"users": users, "jobs": jobs, "active_jobs": active_jobs, "companies": companies}


@router.get("/users")
async def list_users(
    query: str = Query("", max_length=255),
    limit: int = Query(100, ge=1, le=200),
    _: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    statement = select(User).order_by(User.created_at.desc()).limit(limit)
    if query.strip():
        term = f"%{query.strip()}%"
        statement = statement.where(or_(User.email.ilike(term), User.full_name.ilike(term), User.phone_number.ilike(term)))
    return [_user_item(item) for item in (await db.execute(statement)).scalars().all()]


@router.put("/users/{user_id}")
async def update_user(user_id: int, payload: UserAdminUpdate, admin: User = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(404, "Không tìm thấy tài khoản.")
    if target.id == admin.id and (payload.role != "admin" or not payload.is_active):
        raise HTTPException(422, "Bạn không thể tự hạ quyền hoặc vô hiệu hóa tài khoản admin đang sử dụng.")
    if payload.role == "partner":
        if not payload.company_id:
            raise HTTPException(422, "Tài khoản đối tác cần được gán một công ty.")
        company = (await db.execute(select(Company).where(Company.id == payload.company_id))).scalar_one_or_none()
        if company is None:
            raise HTTPException(422, "Công ty được chọn không tồn tại.")
        company.is_partner = True
        target.company_id = company.id
    else:
        target.company_id = None
    target.role, target.is_active = payload.role, payload.is_active
    return _user_item(target)


@router.get("/jobs")
async def list_admin_jobs(
    query: str = Query("", max_length=255),
    limit: int = Query(100, ge=1, le=200),
    _: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    statement = select(Job).options(selectinload(Job.company), selectinload(Job.category)).order_by(Job.created_at.desc()).limit(limit)
    if query.strip():
        term = f"%{query.strip()}%"
        statement = statement.join(Company, isouter=True).where(or_(Job.title.ilike(term), Company.name.ilike(term)))
    jobs = (await db.execute(statement)).scalars().all()
    return [{"id": item.id, "title": item.title, "location": item.location, "salary": item.salary, "experience": item.job_level or item.experience, "job_level": item.job_level, "deadline": item.deadline, "job_url": item.job_url, "company_id": item.company_id, "company_name": item.company.name if item.company else None, "category_id": item.category_id, "category_name": item.category.name if item.category else None, "job_type": item.job_type, "description": item.description, "requirements": item.requirements, "benefits": item.benefits, "is_active": item.is_active} for item in jobs]


@router.put("/jobs/{job_id}")
async def update_job(job_id: int, payload: JobAdminUpdate, _: User = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "Không tìm thấy việc làm.")
    if payload.company_id is not None and not (await db.execute(select(Company.id).where(Company.id == payload.company_id))).scalar_one_or_none():
        raise HTTPException(422, "Công ty được chọn không tồn tại.")
    if payload.category_id is not None and not (await db.execute(select(Category.id).where(Category.id == payload.category_id))).scalar_one_or_none():
        raise HTTPException(422, "Ngành nghề được chọn không tồn tại.")
    values = payload.model_dump()
    submitted_level = values.pop("job_level")
    legacy_level = values.pop("experience")
    selected_level = submitted_level or legacy_level
    if selected_level is not None:
        if selected_level not in JOB_LEVELS:
            raise HTTPException(422, "Cấp bậc không hợp lệ.")
        values["job_level"] = selected_level
    for field, value in values.items():
        setattr(job, field, value)
    return {"message": "Đã cập nhật việc làm.", "id": job.id}


@router.get("/companies")
async def list_admin_companies(
    query: str = Query("", max_length=255),
    limit: int = Query(100, ge=1, le=200),
    _: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    statement = select(Company).order_by(Company.name).limit(limit)
    if query.strip(): statement = statement.where(Company.name.ilike(f"%{query.strip()}%"))
    return [_company_item(item) for item in (await db.execute(statement)).scalars().all()]


@router.post("/companies", status_code=201)
async def create_company(payload: CompanyAdminInput, _: User = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(Company).where(Company.name == payload.name.strip()))).scalar_one_or_none()
    if existing: raise HTTPException(409, "Tên công ty đã tồn tại.")
    item = Company(**payload.model_dump(exclude_none=True, exclude={"name"}), name=payload.name.strip())
    db.add(item); await db.flush()
    return _company_item(item)


@router.put("/companies/{company_id}")
async def update_company(company_id: int, payload: CompanyAdminInput, _: User = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    item = (await db.execute(select(Company).where(Company.id == company_id))).scalar_one_or_none()
    if item is None: raise HTTPException(404, "Không tìm thấy công ty.")
    duplicate = (await db.execute(select(Company.id).where(Company.name == payload.name.strip(), Company.id != company_id))).scalar_one_or_none()
    if duplicate: raise HTTPException(409, "Tên công ty đã tồn tại.")
    for field, value in payload.model_dump().items(): setattr(item, field, value.strip() if field == "name" else value)
    return _company_item(item)
