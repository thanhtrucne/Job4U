from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user, require_roles
from backend.api.profiles import _require_active_consent
from backend.database import get_db
from backend.models import User
from backend.services.structured_matching import normalize_job_skills, recommend_for_profile

router = APIRouter(prefix="/matching", tags=["matching"])


@router.post("/reindex-jd")
async def reindex_jd_skills(_: User = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    return {"normalized_skill_records": await normalize_job_skills(db)}


@router.get("/me")
async def my_recommendations(top_n: int = Query(5, ge=3, le=5), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _require_active_consent(db, user.id, "job_recommend")
    result = await recommend_for_profile(db, user.id, top_n)
    if not result:
        raise HTTPException(404, "Chưa có hồ sơ đã lưu hoặc chưa có tin tuyển dụng đang hiển thị.")
    return {"recommendations": result}
