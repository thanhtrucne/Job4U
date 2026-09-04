"""
Job Recommendation Service - Content-Based Filtering
=====================================================

Su dung TF-IDF Vectorizer + Cosine Similarity de goi y viec lam tuong tu.

Cach hoat dong:
1. Lay tat ca job tu database
2. Tien xu ly van ban: ket hop title + description + requirements + skills
3. Chuyen van ban thanh vector TF-IDF
4. Tinh Cosine Similarity giua job hien tai va cac job khac
5. Tra ve top N job co do tuong dong cao nhat

Caching:
- Ma tran TF-IDF duoc luu trong bo nho (_cache)
- Tu dong reset sau CACHE_TTL_SECONDS (30 phut)
  de dam bao du lieu moi nhat tu DB duoc su dung
"""
import re
import time
import logging
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.models import Job, JobSkill, Skill

logger = logging.getLogger(__name__)

# ── Stop words tieng Viet co ban ─────────────────────────────────────────────
# Day la nhung tu pho bien trong tieng Viet khong mang nhieu y nghia phan biet
VIETNAMESE_STOP_WORDS = {
    "va", "la", "cua", "cho", "trong", "de", "co", "tai", "cac",
    "mot", "nhung", "duoc", "voi", "nhu", "theo", "tu", "khi", "neu",
    "thi", "da", "se", "dang", "bi", "boi", "tren", "duoi", "truoc",
    "sau", "giua", "hoac", "nhung", "nhieu", "it", "that", "rat",
    "hon", "kem", "nhat", "cung", "ca", "moi", "hay", "len", "di",
    "ra", "vao", "an", "uong", "lam", "viec", "lam viec", "cong ty",
    "yeu cau", "kinh nghiem", "ung vien", "nhan vien", "ban", "chung",
    "ban than", "tat ca", "het", "xem", "tat", "chia", "phan",
}

# ── Cache ─────────────────────────────────────────────────────────────────────
CACHE_TTL_SECONDS = 30 * 60  # 30 phut

_cache = {
    "vectorizer": None,       # TfidfVectorizer da fit
    "tfidf_matrix": None,     # Ma tran TF-IDF (n_jobs x n_features)
    "job_ids": None,          # Danh sach job id tuong ung theo thu tu hang
    "job_data": None,         # Dict {job_id: job_info} de tra ve ket qua
    "timestamp": 0.0,         # Thoi diem cap nhat gan nhat
}


# ── Text preprocessing ────────────────────────────────────────────────────────

def preprocess_text(text: Optional[str]) -> str:
    """
    Tien xu ly van ban:
    - Chuyen thanh chu thuong (lowercase)
    - Xoa ky tu dac biet, giu lai chu cai va so
    - Xoa stop words tieng Viet co ban
    - Xoa khoang trang thua
    """
    if not text:
        return ""
    # Lowercase
    text = text.lower()
    # Xoa ky tu dac biet, giu lai chu cai (a-z, tieng Viet), so va khoang trang
    text = re.sub(r"[^a-z0-9\s\u00C0-\u024F\u1E00-\u1EFF]", " ", text)
    # Xoa khoang trang thua
    text = re.sub(r"\s+", " ", text).strip()
    # Loai stop words
    words = text.split()
    words = [w for w in words if w not in VIETNAMESE_STOP_WORDS and len(w) > 1]
    return " ".join(words)


def _build_job_document(job_data: dict) -> str:
    """
    Ket hop cac truong van ban cua mot job thanh mot tai lieu duy nhat.
    
    Chien luoc:
    - title duoc lap lai 3 lan (tang trong so) vi day la truong quan trong nhat
    - skills duoc lap lai 2 lan vi la dac trung ro nhat cua job
    - description va requirements gop vao mot lan
    """
    parts = []

    # Title: lap 3 lan de tang trong so
    title = preprocess_text(job_data.get("title", ""))
    if title:
        parts.extend([title] * 3)

    # Skills: lap 2 lan
    skills_text = preprocess_text(job_data.get("skills", ""))
    if skills_text:
        parts.extend([skills_text] * 2)

    # Category: lap 2 lan
    category = preprocess_text(job_data.get("category", ""))
    if category:
        parts.extend([category] * 2)

    # Description
    desc = preprocess_text(job_data.get("description", ""))
    if desc:
        parts.append(desc)

    # Requirements
    req = preprocess_text(job_data.get("requirements", ""))
    if req:
        parts.append(req)

    # Location
    loc = preprocess_text(job_data.get("location", ""))
    if loc:
        parts.append(loc)

    return " ".join(parts)


# ── Cache management ──────────────────────────────────────────────────────────

def _is_cache_valid() -> bool:
    """Kiem tra cache con hieu luc khong."""
    return (
        _cache["tfidf_matrix"] is not None
        and _cache["job_ids"] is not None
        and (time.time() - _cache["timestamp"]) < CACHE_TTL_SECONDS
    )


def invalidate_cache():
    """Xoa cache thu cong (goi khi co job moi duoc them/xoa)."""
    _cache["vectorizer"] = None
    _cache["tfidf_matrix"] = None
    _cache["job_ids"] = None
    _cache["job_data"] = None
    _cache["timestamp"] = 0.0
    logger.info("[Recommendation] Cache cleared.")


async def _load_and_cache(db: AsyncSession) -> bool:
    """
    Tai tat ca jobs tu DB, build TF-IDF matrix va luu vao cache.
    Returns True neu thanh cong, False neu khong co du lieu.
    """
    result = await db.execute(
        select(Job)
        .where(Job.is_active == True)
        .options(
            selectinload(Job.company),
            selectinload(Job.category),
            selectinload(Job.job_skills).selectinload(JobSkill.skill),
        )
    )
    jobs = result.scalars().all()

    if len(jobs) < 2:
        logger.warning("[Recommendation] Khong du du lieu (can it nhat 2 jobs).")
        return False

    logger.info(f"[Recommendation] Building TF-IDF matrix cho {len(jobs)} jobs...")

    # Chuan bi du lieu
    job_ids = []
    job_data_map = {}
    documents = []

    for job in jobs:
        skills_str = " ".join(js.skill.name for js in job.job_skills if js.skill)
        category_name = job.category.name if job.category else ""
        
        job_info = {
            "id": job.id,
            "title": job.title or "",
            "description": job.description or "",
            "requirements": job.requirements or "",
            "skills": skills_str,
            "category": category_name,
            "location": job.location or "",
        }
        doc = _build_job_document(job_info)
        
        # Luu thong tin de tra ve ket qua
        job_data_map[job.id] = {
            "id": job.id,
            "title": job.title or "",
            "company_name": job.company.name if job.company else None,
            "company_logo": job.company.logo_url if job.company else None,
            "salary": job.salary,
            "location": job.location,
            "experience": job.experience,
            "deadline": job.deadline,
            "job_type": job.job_type,
            "job_url": job.job_url,
            "category": category_name,
        }

        job_ids.append(job.id)
        documents.append(doc)

    # Build TF-IDF Matrix
    # ─────────────────────────────────────────────────────────────────────────
    # TfidfVectorizer chuyen moi job document thanh mot vector so thuc.
    # - min_df=1: giu tu xuat hien it nhat 1 lan
    # - max_df=0.85: bo tu xuat hien trong >85% jobs (qua pho bien, it phan biet)
    # - ngram_range=(1,2): su dung ca unigrams va bigrams: "python", "machine learning"
    # - sublinear_tf=True: dung log(TF) thay vi TF, can bang van ban dai/ngan
    vectorizer = TfidfVectorizer(
        min_df=1,
        max_df=0.85,
        ngram_range=(1, 2),
        sublinear_tf=True,
        max_features=5000,
    )
    tfidf_matrix = vectorizer.fit_transform(documents)
    # ─────────────────────────────────────────────────────────────────────────

    _cache["vectorizer"] = vectorizer
    _cache["tfidf_matrix"] = tfidf_matrix
    _cache["job_ids"] = job_ids
    _cache["job_data"] = job_data_map
    _cache["timestamp"] = time.time()

    logger.info(
        f"[Recommendation] TF-IDF matrix: {tfidf_matrix.shape[0]} jobs x "
        f"{tfidf_matrix.shape[1]} features. Cache updated."
    )
    return True


# ── Main recommendation function ──────────────────────────────────────────────

async def recommend_jobs(
    job_id: int,
    db: AsyncSession,
    top_n: int = 5,
) -> list[dict]:
    """
    Goi y cac viec lam tuong tu voi job_id.

    Thuat toan:
    1. Lay (hoac build) TF-IDF matrix tu cache
    2. Tim hang tuong ung voi job_id trong matrix
    3. Tinh Cosine Similarity giua hang do va tat ca cac hang khac
    4. Sap xep giam dan theo similarity, bo qua chinh job do
    5. Tra ve top_n job voi thong tin day du + similarity_score

    Args:
        job_id: ID cua job can tim goi y
        db: Database session
        top_n: So luong job goi y (mac dinh 5)

    Returns:
        Danh sach dict, moi dict chua thong tin job va similarity_score [0..1]

    Raises:
        ValueError: Neu job_id khong ton tai trong DB
    """
    # Kiem tra / load cache
    if not _is_cache_valid():
        ok = await _load_and_cache(db)
        if not ok:
            return []

    job_ids: list = _cache["job_ids"]
    tfidf_matrix = _cache["tfidf_matrix"]
    job_data_map: dict = _cache["job_data"]

    # Tim vi tri (index) cua job_id trong danh sach
    if job_id not in job_ids:
        # Job_id co the moi duoc them va chua co trong cache -> lam moi cache
        invalidate_cache()
        ok = await _load_and_cache(db)
        if not ok or job_id not in _cache["job_ids"]:
            raise ValueError(f"Job ID {job_id} khong ton tai hoac khong active.")
        job_ids = _cache["job_ids"]
        tfidf_matrix = _cache["tfidf_matrix"]
        job_data_map = _cache["job_data"]

    idx = job_ids.index(job_id)

    # ─── Cosine Similarity ────────────────────────────────────────────────────
    # cosine_similarity tra ve ma tran (1 x n_jobs)
    # Moi phan tu la do tuong dong [0..1] giua job[idx] va cac job khac
    job_vector = tfidf_matrix[idx]          # Vector TF-IDF cua job hien tai
    sim_scores = cosine_similarity(job_vector, tfidf_matrix).flatten()
    # ─────────────────────────────────────────────────────────────────────────

    # Sap xep giam dan theo similarity score
    # argsort tra ve chi so tang dan -> [::-1] dao nguoc
    sorted_indices = np.argsort(sim_scores)[::-1]

    results = []
    for i in sorted_indices:
        jid = job_ids[i]
        if jid == job_id:
            continue  # Bo qua chinh job dang xem
        if len(results) >= top_n:
            break

        score = float(sim_scores[i])
        if score <= 0:
            break  # Bo qua cac job hoan toan khong lien quan

        info = job_data_map.get(jid, {}).copy()
        info["similarity_score"] = round(score, 4)
        results.append(info)

    logger.info(
        f"[Recommendation] job_id={job_id}: tim duoc {len(results)} goi y "
        f"(top_n={top_n})"
    )
    return results
