"""Applicant account dashboard and personal-profile API."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.config import settings
from backend.database import get_db
from backend.models import CandidateProfile, User
from backend.schemas import CandidateDashboardInput

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _encryption_key() -> str:
    # Deployments should set DOCUMENT_ENCRYPTION_KEY. SECRET_KEY is a backwards-
    # compatible fallback so existing local installations do not write plaintext.
    return settings.DOCUMENT_ENCRYPTION_KEY or settings.SECRET_KEY


async def _identity_number(db: AsyncSession, user_id: int) -> str | None:
    try:
        return (await db.execute(text("""
            SELECT pgp_sym_decrypt(decode(identity_document_number_encrypted, 'base64'), :key)
            FROM candidate_profiles WHERE user_id = :user_id
        """), {"key": _encryption_key(), "user_id": user_id})).scalar_one_or_none()
    except Exception:
        # Old/corrupt ciphertext must not block the rest of the account page.
        return None


def _profile_data(profile: CandidateProfile | None) -> dict:
    if profile is None:
        return {}
    fields = (
        "nationality", "date_of_birth", "gender", "place_of_birth", "marital_status",
        "height_cm", "weight_kg", "driving_license_type", "contact_address", "province", "ward",
        "education_level", "education_grade", "specialization", "training_institution",
        "foreign_language", "foreign_language_school", "computer_skill", "computer_school",
        "years_experience", "work_experience", "workplace", "identity_issue_date",
        "identity_issue_place", "religion", "ethnicity", "employment_status", "notes",
    )
    return {field: getattr(profile, field) for field in fields}


@router.get("/me")
async def get_my_dashboard(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))).scalar_one_or_none()
    return {
        "account": {"full_name": user.full_name, "phone_number": user.phone_number, "email": user.email},
        "profile": {**_profile_data(profile), "identity_document_number": await _identity_number(db, user.id) if profile else None},
    }


@router.put("/me")
async def save_my_dashboard(payload: CandidateDashboardInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))).scalar_one_or_none()
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.phone_number is not None:
        normalized_phone = func.regexp_replace(User.phone_number, "[^0-9]", "", "g")
        phone_in_use = (await db.execute(
            select(User.id).where(normalized_phone == payload.phone_number, User.id != user.id)
        )).scalar_one_or_none()
        if phone_in_use is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Số điện thoại đã được đăng ký bởi tài khoản khác.")
        user.phone_number = payload.phone_number
    values = payload.model_dump(exclude={"identity_document_number", "full_name", "phone_number"})
    if profile is None:
        profile = CandidateProfile(user_id=user.id, **values)
        db.add(profile)
        await db.flush()
    else:
        for field, value in values.items():
            setattr(profile, field, value)
        await db.flush()

    # Store only ciphertext for identity number. Empty form input clears it.
    if payload.identity_document_number:
        await db.execute(text("""
            UPDATE candidate_profiles
            SET identity_document_number_encrypted = encode(pgp_sym_encrypt(:value, :key), 'base64')
            WHERE user_id = :user_id
        """), {"value": payload.identity_document_number.strip(), "key": _encryption_key(), "user_id": user.id})
    elif "identity_document_number" in payload.model_fields_set:
        await db.execute(text("UPDATE candidate_profiles SET identity_document_number_encrypted = NULL WHERE user_id = :user_id"), {"user_id": user.id})
    return {
        "message": "Đã lưu thông tin tài khoản.",
        "account": {"full_name": user.full_name, "phone_number": user.phone_number, "email": user.email},
        "profile": {**_profile_data(profile), "identity_document_number": await _identity_number(db, user.id)},
    }
