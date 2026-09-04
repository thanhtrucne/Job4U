"""Explainable matching based on normalized skills, TF-IDF and simple business rules."""
from __future__ import annotations

import re
from collections import defaultdict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import DigitalProfile, Job, JobSkillRequirement, ProfileSkill, Skill

# Kept deliberately small and editable for a graduation project; skill names remain the source of truth.
SKILL_ALIASES = {"js": "javascript", "node": "node.js", "postgres": "postgresql", "aws cloud": "aws", "reactjs": "react"}
REQUIRED_WEIGHT, PREFERRED_WEIGHT = 1.0, 0.55


def _normalized(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _section(text: str, labels: tuple[str, ...]) -> str:
    """Best-effort section split: crawled JDs do not have a fixed format."""
    lower = _normalized(text)
    starts = [lower.find(label) for label in labels if lower.find(label) >= 0]
    if not starts:
        return ""
    start = min(starts)
    tail = lower[start:]
    end_candidates = [tail.find(label) for label in ("quyền lợi", "benefit", "mô tả", "responsibilities", "ưu tiên", "preferred") if tail.find(label) > 20]
    return tail[:min(end_candidates)] if end_candidates else tail


def _extract_named_skills(text: str, catalogue: dict[str, int]) -> set[int]:
    text = _normalized(text)
    found = set()
    for alias, canonical in SKILL_ALIASES.items():
        text = re.sub(rf"(?<!\w){re.escape(alias)}(?!\w)", canonical, text)
    for name, skill_id in catalogue.items():
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text):
            found.add(skill_id)
    return found


async def normalize_job_skills(db: AsyncSession, jobs: list[Job] | None = None) -> int:
    """Use TF-IDF to weight detected catalogue skills and label required/preferred sections."""
    catalogue_rows = (await db.execute(select(Skill))).scalars().all()
    catalogue = {_normalized(skill.name): skill.id for skill in catalogue_rows}
    if jobs is None:
        jobs = (await db.execute(select(Job).where(Job.is_active.is_(True)))).scalars().all()
    documents = [_normalized(" ".join([job.title or "", job.description or "", job.requirements or ""])) for job in jobs]
    if not documents or not catalogue:
        return 0
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), lowercase=True, token_pattern=r"(?u)\b[\w.+#-]+\b")
    matrix = vectorizer.fit_transform(documents)
    terms = {term: index for index, term in enumerate(vectorizer.get_feature_names_out())}
    changed = 0
    for row_index, job in enumerate(jobs):
        required_text = _section(job.requirements or job.description or "", ("yêu cầu", "requirements", "requirement", "must have")) or (job.requirements or job.description or "")
        preferred_text = _section(job.requirements or job.description or "", ("ưu tiên", "preferred", "nice to have"))
        required = _extract_named_skills(required_text, catalogue)
        preferred = _extract_named_skills(preferred_text, catalogue) - required
        all_found = required | preferred
        await db.execute(JobSkillRequirement.__table__.delete().where(JobSkillRequirement.job_id == job.id))
        for normalized_name, skill_id in catalogue.items():
            if skill_id not in all_found:
                continue
            term_index = terms.get(normalized_name)
            tfidf = float(matrix[row_index, term_index]) if term_index is not None else 0.1
            db.add(JobSkillRequirement(job_id=job.id, skill_id=skill_id, importance="required" if skill_id in required else "preferred", tfidf_weight=max(tfidf, 0.1)))
            changed += 1
    return changed


def _experience_score(profile_years: float, job_experience: str | None) -> float:
    numbers = [float(value) for value in re.findall(r"\d+(?:[.,]\d+)?", _normalized(job_experience).replace(",", "."))]
    if not numbers:
        return 1.0
    required = min(numbers)
    return min(profile_years / required, 1.0) if required else 1.0


def _location_score(desired: str | None, job_location: str | None) -> float:
    return 1.0 if not desired or _normalized(desired) in _normalized(job_location) else 0.0


def _salary_score(profile: DigitalProfile, job_salary: str | None) -> float:
    text = _normalized(job_salary)
    raw_values = re.findall(r"\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?", text)
    values = []
    for value in raw_values:
        compact = value.replace(".", "").replace(",", "")
        amount = float(compact)
        # Values below 1,000 are conventionally salary-in-millions (e.g. 15-20).
        values.append(amount if amount < 1_000 else amount / 1_000_000)
    if not profile.desired_salary_min or not values:
        return 0.5
    # Salary crawler formats vary (e.g. 15-25 triệu); use its maximum as a transparent approximation.
    return 1.0 if max(values) >= profile.desired_salary_min else 0.0


def _title_score(profile: DigitalProfile, job: Job) -> float:
    desired = {item for item in re.findall(r"\w+", _normalized(profile.headline)) if len(item) > 2}
    offered = {item for item in re.findall(r"\w+", _normalized(job.title)) if len(item) > 2}
    if not desired or not offered:
        return 0.0
    return len(desired & offered) / max(len(desired), len(offered))


async def recommend_for_profile(db: AsyncSession, user_id: int, top_n: int = 5) -> list[dict]:
    profile = (await db.execute(select(DigitalProfile).options(selectinload(DigitalProfile.skills).selectinload(ProfileSkill.skill)).where(DigitalProfile.user_id == user_id))).scalar_one_or_none()
    if profile is None:
        return []
    jobs = (await db.execute(select(Job).options(selectinload(Job.company)).where(Job.is_active.is_(True)))).scalars().all()
    reqs = (await db.execute(select(JobSkillRequirement))).scalars().all()
    by_job: dict[int, list[JobSkillRequirement]] = defaultdict(list)
    for req in reqs: by_job[req.job_id].append(req)
    user_skills = {item.skill_id: (item.proficiency or 3) / 5 for item in profile.skills}
    ranked = []
    for job in jobs:
        requirements = by_job.get(job.id, [])
        ids = [item.skill_id for item in requirements]
        if requirements:
            weights = np.array([item.tfidf_weight * (REQUIRED_WEIGHT if item.importance == "required" else PREFERRED_WEIGHT) for item in requirements])
            candidate = np.array([user_skills.get(skill_id, 0.0) for skill_id in ids])
            similarity = float(cosine_similarity(candidate.reshape(1, -1), weights.reshape(1, -1))[0, 0]) if candidate.any() else 0.0
        else:
            similarity = 0.0
        exp, location, salary = _experience_score(profile.years_experience, job.experience), _location_score(profile.desired_location, job.location), _salary_score(profile, job.salary)
        level = 1.0 if profile.desired_job_level and profile.desired_job_level == job.job_level else 0.0
        job_type = 1.0 if profile.desired_job_type and profile.desired_job_type == job.job_type else 0.0
        title = _title_score(profile, job)
        total = (
            100 * (0.70 * similarity + 0.15 * exp + 0.10 * location + 0.05 * salary)
            if requirements else 100 * (0.45 * title + 0.15 * exp + 0.15 * location + 0.10 * salary + 0.075 * level + 0.075 * job_type)
        )
        matched = [skill_id for skill_id in ids if skill_id in user_skills]
        ranked.append({"job_id": job.id, "title": job.title, "company": job.company.name if job.company else None, "is_partner": bool(job.company and job.company.is_partner), "job_url": job.job_url, "score": round(total, 2), "matched_skill_ids": matched, "score_breakdown": {"skill_cosine": round(similarity * 100, 2), "title": round(title * 100, 2), "experience": round(exp * 100, 2), "location": round(location * 100, 2), "salary": round(salary * 100, 2), "job_level": round(level * 100, 2), "job_type": round(job_type * 100, 2)}})
    return sorted(ranked, key=lambda item: item["score"], reverse=True)[:top_n]
