"""Public career handbook and administrator content management."""
import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.auth import get_current_user, require_roles
from backend.database import get_db
from backend.models import CareerGuide, CareerGuideCategory, SavedCareerGuide, User

router = APIRouter(prefix="/career-guides", tags=["career-handbook"])
admin_router = APIRouter(prefix="/admin/career-guides", tags=["admin", "career-handbook"])

def slugify(value: str) -> str:
    import unicodedata
    value = unicodedata.normalize("NFD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", value)) or "cam-nang"

def item(guide: CareerGuide, saved: bool = False) -> dict:
    return {"id":guide.id,"title":guide.title,"slug":guide.slug,"thumbnail_url":guide.thumbnail_url,"summary":guide.summary,"content":guide.content,"category":{"id":guide.category.id,"name":guide.category.name,"slug":guide.category.slug},"author":guide.author_name or (guide.author.full_name if guide.author else "Job4U"),"tags":guide.tags or [],"status":str(guide.status),"is_featured":guide.is_featured,"view_count":guide.view_count,"save_count":getattr(guide,"save_count",0),"created_at":guide.created_at,"updated_at":guide.updated_at,"saved":saved}

class GuideInput(BaseModel):
    title: str = Field(min_length=4, max_length=300)
    thumbnail_url: str | None = Field(default=None, max_length=2000)
    summary: str = Field(min_length=20, max_length=1000)
    content: str = Field(min_length=20, max_length=50000)
    category_id: int
    tags: list[str] = []
    status: Literal["draft","published","hidden"] = "draft"
    is_featured: bool = False
    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value): return list(dict.fromkeys(tag.strip()[:60] for tag in value if tag.strip()))[:12]

class CategoryInput(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=500)

@router.get("/categories")
async def categories(db: AsyncSession = Depends(get_db)):
    rows=(await db.execute(select(CareerGuideCategory).order_by(CareerGuideCategory.id))).scalars().all()
    return [{"id":row.id,"name":row.name,"slug":row.slug,"description":row.description} for row in rows]

@router.get("")
async def list_guides(query: str = Query("", max_length=150), category: str = Query("", max_length=180), page: int = Query(1, ge=1), page_size: int = Query(9, ge=1, le=24), db: AsyncSession = Depends(get_db)):
    stmt=select(CareerGuide).options(selectinload(CareerGuide.category),selectinload(CareerGuide.author)).where(CareerGuide.status=="published")
    if category: stmt=stmt.join(CareerGuideCategory).where(CareerGuideCategory.slug==category)
    if query.strip():
        term=f"%{query.strip()}%"; stmt=stmt.where(or_(CareerGuide.title.ilike(term),CareerGuide.summary.ilike(term),CareerGuide.content.ilike(term)))
    total=(await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows=(await db.execute(stmt.order_by(CareerGuide.is_featured.desc(),CareerGuide.created_at.desc()).offset((page-1)*page_size).limit(page_size))).scalars().all()
    save_counts=dict((await db.execute(select(SavedCareerGuide.career_guide_id,func.count()).group_by(SavedCareerGuide.career_guide_id))).all())
    for row in rows: row.save_count=save_counts.get(row.id,0)
    return {"items":[item(row) for row in rows],"total":total,"page":page,"page_size":page_size}

@router.get("/{slug}")
async def guide_detail(slug: str, db: AsyncSession = Depends(get_db)):
    guide=(await db.execute(select(CareerGuide).options(selectinload(CareerGuide.category),selectinload(CareerGuide.author)).where(CareerGuide.slug==slug,CareerGuide.status=="published"))).scalar_one_or_none()
    if not guide: raise HTTPException(404,"Không tìm thấy bài viết.")
    guide.view_count += 1
    saved=False
    guide.save_count=(await db.execute(select(func.count()).select_from(SavedCareerGuide).where(SavedCareerGuide.career_guide_id==guide.id))).scalar_one()
    related=(await db.execute(select(CareerGuide).options(selectinload(CareerGuide.category),selectinload(CareerGuide.author)).where(CareerGuide.status=="published",CareerGuide.category_id==guide.category_id,CareerGuide.id!=guide.id).order_by(CareerGuide.created_at.desc()).limit(3))).scalars().all()
    return {"guide":item(guide,saved),"related":[item(row) for row in related]}

@router.post("/{guide_id}/save")
async def save_guide(guide_id:int,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    if not (await db.execute(select(CareerGuide.id).where(CareerGuide.id==guide_id,CareerGuide.status=="published"))).scalar_one_or_none(): raise HTTPException(404,"Không tìm thấy bài viết.")
    existing=(await db.execute(select(SavedCareerGuide).where(SavedCareerGuide.user_id==user.id,SavedCareerGuide.career_guide_id==guide_id))).scalar_one_or_none()
    if existing: await db.delete(existing); return {"saved":False}
    db.add(SavedCareerGuide(user_id=user.id,career_guide_id=guide_id)); return {"saved":True}

@admin_router.get("")
async def admin_list(_:User=Depends(require_roles("admin")),db:AsyncSession=Depends(get_db)):
    rows=(await db.execute(select(CareerGuide).options(selectinload(CareerGuide.category),selectinload(CareerGuide.author)).order_by(CareerGuide.updated_at.desc().nullslast(),CareerGuide.created_at.desc()))).scalars().all()
    counts=dict((await db.execute(select(SavedCareerGuide.career_guide_id,func.count()).group_by(SavedCareerGuide.career_guide_id))).all())
    for row in rows: row.save_count=counts.get(row.id,0)
    return [item(row) for row in rows]

@admin_router.post("",status_code=201)
async def create(payload:GuideInput,admin:User=Depends(require_roles("admin")),db:AsyncSession=Depends(get_db)):
    if not (await db.execute(select(CareerGuideCategory.id).where(CareerGuideCategory.id==payload.category_id))).scalar_one_or_none(): raise HTTPException(422,"Danh mục không tồn tại.")
    base=slugify(payload.title); slug=base; n=2
    while (await db.execute(select(CareerGuide.id).where(CareerGuide.slug==slug))).scalar_one_or_none(): slug=f"{base}-{n}"; n+=1
    guide=CareerGuide(**payload.model_dump(),slug=slug,author_id=admin.id,author_name=admin.full_name or admin.email)
    db.add(guide);await db.flush();return {"id":guide.id,"slug":guide.slug}

@admin_router.put("/{guide_id}")
async def update(guide_id:int,payload:GuideInput,_:User=Depends(require_roles("admin")),db:AsyncSession=Depends(get_db)):
    guide=(await db.execute(select(CareerGuide).where(CareerGuide.id==guide_id))).scalar_one_or_none()
    if not guide: raise HTTPException(404,"Không tìm thấy bài viết.")
    for key,value in payload.model_dump().items(): setattr(guide,key,value)
    guide.updated_at=datetime.now(timezone.utc);return {"id":guide.id,"message":"Đã lưu bài viết."}

@admin_router.delete("/{guide_id}",status_code=204)
async def delete_guide(guide_id:int,_:User=Depends(require_roles("admin")),db:AsyncSession=Depends(get_db)):
    guide=(await db.execute(select(CareerGuide).where(CareerGuide.id==guide_id))).scalar_one_or_none()
    if not guide: raise HTTPException(404,"Không tìm thấy bài viết.")
    await db.delete(guide)

@admin_router.post("/categories",status_code=201)
async def create_category(name:str,description:str|None=None,_:User=Depends(require_roles("admin")),db:AsyncSession=Depends(get_db)):
    slug=slugify(name)
    if (await db.execute(select(CareerGuideCategory.id).where(or_(CareerGuideCategory.name==name,CareerGuideCategory.slug==slug)))).scalar_one_or_none(): raise HTTPException(409,"Danh mục đã tồn tại.")
    row=CareerGuideCategory(name=name,slug=slug,description=description);db.add(row);await db.flush();return {"id":row.id,"name":row.name,"slug":row.slug}

@admin_router.put("/categories/{category_id}")
async def update_category(category_id: int, payload: CategoryInput, _:User=Depends(require_roles("admin")),db:AsyncSession=Depends(get_db)):
    row=(await db.execute(select(CareerGuideCategory).where(CareerGuideCategory.id==category_id))).scalar_one_or_none()
    if not row: raise HTTPException(404,"Category not found.")
    name=payload.name.strip(); slug=slugify(name)
    duplicate=(await db.execute(select(CareerGuideCategory.id).where(CareerGuideCategory.id!=category_id,or_(CareerGuideCategory.name==name,CareerGuideCategory.slug==slug)))).scalar_one_or_none()
    if duplicate: raise HTTPException(409,"Category already exists.")
    row.name=name; row.slug=slug; row.description=payload.description
    return {"id":row.id,"name":row.name,"slug":row.slug,"description":row.description}

@admin_router.delete("/categories/{category_id}",status_code=204)
async def delete_category(category_id: int, _:User=Depends(require_roles("admin")),db:AsyncSession=Depends(get_db)):
    row=(await db.execute(select(CareerGuideCategory).where(CareerGuideCategory.id==category_id))).scalar_one_or_none()
    if not row: raise HTTPException(404,"Category not found.")
    used=(await db.execute(select(func.count()).select_from(CareerGuide).where(CareerGuide.category_id==category_id))).scalar_one()
    if used: raise HTTPException(409,"Cannot delete a category containing articles.")
    await db.delete(row)
