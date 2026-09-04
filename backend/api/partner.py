"""Partner-only job publishing and applicant overview APIs."""
from datetime import date
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import require_roles
from backend.database import get_db
from backend.models import Application, Company, Consent, DigitalProfile, Job, User

router = APIRouter(prefix="/partner", tags=["partner"])
JOB_LEVELS = {"Nhân viên", "Trưởng nhóm", "Trưởng / Phó phòng", "Quản lý / Giám sát", "Trưởng chi nhánh", "Phó giám đốc", "Giám đốc", "Thực tập sinh"}


class PartnerJobInput(BaseModel):
    title: str = Field(min_length=1, max_length=2000)
    location: str | None = None
    salary: str | None = None
    experience: str | None = None
    job_level: str | None = None
    deadline: str | None = None
    job_type: str | None = None
    description: str | None = None
    requirements: str | None = None
    benefits: str | None = None
    is_active: bool = True

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, value: str | None) -> str | None:
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
    def validate_salary(cls, value: str | None) -> str | None:
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


def _require_company(user: User) -> int:
    if not user.company_id:
        raise HTTPException(403, "Tài khoản doanh nghiệp chưa được gán công ty.")
    return user.company_id


def _job_item(job: Job, applications: int = 0) -> dict:
    return {"id": job.id, "title": job.title, "location": job.location, "salary": job.salary,
            "experience": job.job_level or job.experience, "job_level": job.job_level, "deadline": job.deadline, "job_type": job.job_type,
            "description": job.description, "requirements": job.requirements, "benefits": job.benefits,
            "is_active": job.is_active, "applications": applications}


def _normalized(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def _candidate_score(job: Job, profile: DigitalProfile) -> tuple[int, list[str]]:
    score, reasons = 0, []
    title_words = {word for word in re.findall(r"\w+", _normalized(job.title)) if len(word) > 2}
    candidate_words = {word for word in re.findall(r"\w+", _normalized(profile.headline)) if len(word) > 2}
    if title_words and candidate_words:
        overlap = len(title_words & candidate_words) / max(len(title_words), len(candidate_words))
        if overlap:
            score += round(45 * overlap); reasons.append("Vị trí phù hợp")
    if profile.desired_location and job.location and _normalized(profile.desired_location) in _normalized(job.location):
        score += 20; reasons.append("Địa điểm phù hợp")
    if profile.desired_job_level and job.job_level and profile.desired_job_level == job.job_level:
        score += 15; reasons.append("Cấp bậc phù hợp")
    if profile.desired_job_type and job.job_type and profile.desired_job_type == job.job_type:
        score += 15; reasons.append("Loại hình phù hợp")
    salary_values = [int(value.replace(".", "").replace(",", "")) for value in re.findall(r"\d{1,3}(?:[.,]\d{3})+|\d+", job.salary or "")]
    if salary_values and profile.desired_salary_min is not None:
        if max(salary_values) >= profile.desired_salary_min * 1_000_000:
            score += 5; reasons.append("Mức lương phù hợp")
    return score, reasons


@router.get("/jobs/{job_id}/matching-candidates")
async def matching_candidates(job_id: int, user: User = Depends(require_roles("partner")), db: AsyncSession = Depends(get_db)):
    """Return only candidates who granted the general company-sharing consent."""
    company_id = _require_company(user)
    job = (await db.execute(select(Job).where(Job.id == job_id, Job.company_id == company_id))).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "Không tìm thấy tin tuyển dụng của doanh nghiệp.")
    rows = (await db.execute(
        select(DigitalProfile, User)
        .join(User, User.id == DigitalProfile.user_id)
        .join(Consent, (Consent.user_id == DigitalProfile.user_id) & (Consent.purpose == "share_with_company"))
        .where(User.is_active.is_(True), Consent.granted_at.is_not(None), Consent.revoked_at.is_(None))
        .limit(250)
    )).all()
    candidates = []
    for profile, candidate in rows:
        score, reasons = _candidate_score(job, profile)
        if score < 20:
            continue
        candidates.append({
            "user_id": candidate.id, "full_name": candidate.full_name, "headline": profile.headline,
            "desired_location": profile.desired_location, "desired_job_level": profile.desired_job_level,
            "desired_job_type": profile.desired_job_type, "score": score, "reasons": reasons,
        })
    candidates.sort(key=lambda item: item["score"], reverse=True)
    return {"job_id": job.id, "job_title": job.title, "candidates": candidates[:30]}


@router.get("/dashboard")
async def dashboard(user: User = Depends(require_roles("partner")), db: AsyncSession = Depends(get_db)):
    company_id = _require_company(user)
    company = (await db.execute(select(Company).where(Company.id == company_id))).scalar_one_or_none()
    if company is None:
        raise HTTPException(404, "Không tìm thấy doanh nghiệp.")
    jobs = (await db.execute(select(Job).where(Job.company_id == company_id).order_by(Job.created_at.desc()))).scalars().all()
    counts = dict((await db.execute(select(Application.job_id, func.count(Application.id)).where(Application.company_id == company_id).group_by(Application.job_id))).all())
    applications = (await db.execute(select(Application).where(Application.company_id == company_id))).scalars().all()
    return {
        "company": {"id": company.id, "name": company.name, "industry": company.industry, "location": company.location},
        "summary": {"jobs": len(jobs), "active_jobs": sum(bool(job.is_active) for job in jobs), "applications": len(applications), "pending": sum(item.status == "pending" for item in applications)},
        "jobs": [_job_item(job, counts.get(job.id, 0)) for job in jobs],
    }


@router.post("/jobs", status_code=201)
async def create_job(payload: PartnerJobInput, user: User = Depends(require_roles("partner")), db: AsyncSession = Depends(get_db)):
    company_id = _require_company(user)
    values = payload.model_dump()
    submitted_level = values.pop("job_level")
    legacy_level = values.pop("experience")
    selected_level = submitted_level or legacy_level
    if selected_level is not None:
        if selected_level not in JOB_LEVELS:
            raise HTTPException(422, "Cấp bậc không hợp lệ.")
        values["job_level"] = selected_level
    job = Job(company_id=company_id, job_url=f"portal://partner-job/{uuid4()}", **values)
    db.add(job)
    await db.flush()
    return _job_item(job)


@router.put("/jobs/{job_id}")
async def update_job(job_id: int, payload: PartnerJobInput, user: User = Depends(require_roles("partner")), db: AsyncSession = Depends(get_db)):
    company_id = _require_company(user)
    job = (await db.execute(select(Job).where(Job.id == job_id, Job.company_id == company_id))).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "Không tìm thấy tin tuyển dụng của doanh nghiệp.")
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
    return _job_item(job)
