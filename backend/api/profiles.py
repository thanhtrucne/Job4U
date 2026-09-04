"""Applicant-owned structured CV and consent APIs."""
from io import BytesIO
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.auth import get_current_user
from backend.database import get_db
from backend.models import CandidateProfile, Consent, DigitalProfile, Document, ProfileSkill, Skill, User
from backend.services.object_storage import delete_document
from backend.schemas import ConsentInput, DigitalProfileInput

router = APIRouter(tags=["profiles", "privacy"])


async def _require_active_consent(db: AsyncSession, user_id: int, purpose: str) -> None:
    consent = (await db.execute(select(Consent).where(Consent.user_id == user_id, Consent.purpose == purpose))).scalar_one_or_none()
    if consent is None or consent.granted_at is None or consent.revoked_at is not None:
        raise HTTPException(403, "Bạn cần đồng ý riêng cho mục đích này trước khi tiếp tục.")


@router.get("/profile/skills")
async def list_profile_skills(db: AsyncSession = Depends(get_db)):
    """The canonical skill catalogue shared by profile form and JD normalization."""
    skills = (await db.execute(select(Skill).order_by(Skill.name))).scalars().all()
    return [{"id": item.id, "name": item.name} for item in skills]


@router.get("/profile/me")
async def get_profile(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(DigitalProfile).options(selectinload(DigitalProfile.skills).selectinload(ProfileSkill.skill)).where(DigitalProfile.user_id == user.id))).scalar_one_or_none()
    if profile is None:
        return None
    return {
        "id": profile.id, "headline": profile.headline, "industry": profile.industry,
        "desired_location": profile.desired_location, "desired_salary_min": profile.desired_salary_min,
        "desired_salary_max": profile.desired_salary_max, "desired_job_level": profile.desired_job_level,
        "desired_job_type": profile.desired_job_type, "years_experience": profile.years_experience,
        "education": profile.education, "summary": profile.summary,
        "skills": [{"skill_id": row.skill_id, "name": row.skill.name, "proficiency": row.proficiency} for row in profile.skills],
    }


@router.put("/profile/me")
async def save_profile(payload: DigitalProfileInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not payload.policy_accepted:
        raise HTTPException(422, "Bạn cần đồng ý Chính sách dữ liệu cá nhân để lưu hồ sơ.")
    for purpose in ("create_profile", "job_recommend"):
        consent = (await db.execute(select(Consent).where(Consent.user_id == user.id, Consent.purpose == purpose))).scalar_one_or_none()
        if consent is None:
            consent = Consent(user_id=user.id, purpose=purpose, consent_text_version="2026.3")
            db.add(consent)
        consent.granted_at, consent.revoked_at, consent.consent_text_version = datetime.now(timezone.utc), None, "2026.3"
    if (
        payload.years_experience < 0
        or any(value is not None and value < 1 for value in (payload.desired_salary_min, payload.desired_salary_max))
        or (payload.desired_salary_min and payload.desired_salary_max and payload.desired_salary_min > payload.desired_salary_max)
    ):
        raise HTTPException(422, "Dữ liệu kinh nghiệm hoặc mức lương không hợp lệ.")
    skill_ids = list({entry.skill_id for entry in payload.skills})
    if len(skill_ids) != len(payload.skills):
        raise HTTPException(422, "Mỗi kỹ năng chỉ được chọn một lần.")
    known = set((await db.execute(select(Skill.id).where(Skill.id.in_(skill_ids)))).scalars()) if skill_ids else set()
    if len(known) != len(skill_ids):
        raise HTTPException(422, "Có kỹ năng không thuộc danh mục chuẩn.")
    profile = (await db.execute(select(DigitalProfile).where(DigitalProfile.user_id == user.id))).scalar_one_or_none()
    values = payload.model_dump(exclude={"skills", "policy_accepted"})
    if profile is None:
        profile = DigitalProfile(user_id=user.id, **values)
        db.add(profile)
        await db.flush()
    else:
        for key, value in values.items():
            setattr(profile, key, value)
        await db.execute(delete(ProfileSkill).where(ProfileSkill.profile_id == profile.id))
    db.add_all([ProfileSkill(profile_id=profile.id, skill_id=item.skill_id, proficiency=item.proficiency) for item in payload.skills])
    await db.flush()
    return {"id": profile.id, "message": "Đã lưu hồ sơ số."}


@router.get("/profile/me/pdf")
async def export_profile_pdf(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Generate a polished printable CV from the user's structured profile."""
    profile = await get_profile(user, db)
    if profile is None:
        raise HTTPException(404, "Bạn chưa tạo hồ sơ số.")
    from html import escape
    import os

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    candidate = (await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    )).scalar_one_or_none()

    font, bold_font = "Helvetica", "Helvetica-Bold"
    arial = "C:/Windows/Fonts/arial.ttf"
    arial_bold = "C:/Windows/Fonts/arialbd.ttf"
    if os.path.exists(arial) and os.path.exists(arial_bold):
        pdfmetrics.registerFont(TTFont("Arial", arial))
        pdfmetrics.registerFont(TTFont("Arial-Bold", arial_bold))
        font = "Arial"
        bold_font = "Arial-Bold"

    palette = {"green": colors.HexColor("#008F60"), "deep": colors.HexColor("#173B32"), "text": colors.HexColor("#27363B"), "muted": colors.HexColor("#617177"), "line": colors.HexColor("#DCEAE4"), "soft": colors.HexColor("#EFF8F4")}
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CVName", parent=styles["Normal"], fontName=bold_font, fontSize=23, leading=27, textColor=colors.white))
    styles.add(ParagraphStyle(name="CVRole", parent=styles["Normal"], fontName=font, fontSize=11, leading=15, textColor=colors.HexColor("#D9FFF0")))
    styles.add(ParagraphStyle(name="CVContact", parent=styles["Normal"], fontName=font, fontSize=8.8, leading=13, textColor=colors.HexColor("#E8FFF6")))
    styles.add(ParagraphStyle(name="CVSection", parent=styles["Normal"], fontName=bold_font, fontSize=11, leading=15, textColor=palette["green"], spaceBefore=5, spaceAfter=5))
    styles.add(ParagraphStyle(name="CVBody", parent=styles["Normal"], fontName=font, fontSize=9.2, leading=15, textColor=palette["text"]))
    styles.add(ParagraphStyle(name="CVLabel", parent=styles["Normal"], fontName=bold_font, fontSize=8.3, leading=11, textColor=palette["muted"]))
    styles.add(ParagraphStyle(name="CVValue", parent=styles["Normal"], fontName=font, fontSize=9.4, leading=13, textColor=palette["text"]))

    def safe(value: object, fallback: str = "Chưa cập nhật") -> str:
        text = str(value).strip() if value is not None else ""
        return escape(text or fallback).replace("\n", "<br/>")

    def section(title: str):
        return [Spacer(1, 4), Paragraph(title, styles["CVSection"]), HRFlowable(width="100%", thickness=0.7, color=palette["line"], spaceAfter=8)]

    def field(label: str, value: object):
        return [Paragraph(label, styles["CVLabel"]), Paragraph(safe(value), styles["CVValue"])]

    location = ", ".join(part for part in [getattr(candidate, "province", None), getattr(candidate, "ward", None)] if part)
    contact_parts = [user.email, user.phone_number, getattr(candidate, "contact_address", None), location]
    contact = " &nbsp;•&nbsp; ".join(escape(str(item)) for item in contact_parts if item)
    initials = "".join(word[0].upper() for word in (user.full_name or "Ứng viên").split()[:2])
    header = Table([[Paragraph(initials, ParagraphStyle(name="CVInitials", parent=styles["Normal"], fontName=bold_font, fontSize=18, leading=22, alignment=TA_LEFT, textColor=palette["green"])), [Paragraph(safe(user.full_name, "Ứng viên Job4U"), styles["CVName"]), Paragraph(safe(profile.get("headline"), "Hồ sơ việc làm số"), styles["CVRole"]), Paragraph(contact or "Thông tin liên hệ đang được cập nhật", styles["CVContact"])]]], colWidths=[25 * mm, 145 * mm])
    header.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), palette["deep"]), ("BACKGROUND", (0, 0), (0, 0), colors.white), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14), ("BOX", (0, 0), (0, 0), 0, colors.white), ("ALIGN", (0, 0), (0, 0), "CENTER"), ("VALIGN", (0, 0), (0, 0), "MIDDLE")]))

    skills = ", ".join(item["name"] for item in profile.get("skills", [])) or "Chưa cập nhật"
    target_table = Table([[field("VỊ TRÍ MONG MUỐN", profile.get("headline")), field("NGÀNH NGHỀ", profile.get("industry"))], [field("ĐỊA ĐIỂM MONG MUỐN", profile.get("desired_location")), field("MỨC LƯƠNG MONG MUỐN", (f"{profile['desired_salary_min']:g} – {profile['desired_salary_max']:g} triệu VNĐ" if profile.get("desired_salary_min") is not None and profile.get("desired_salary_max") is not None else (f"Từ {profile['desired_salary_min']:g} triệu VNĐ" if profile.get("desired_salary_min") is not None else "Chưa cập nhật"))) ]], colWidths=[85 * mm, 85 * mm])
    target_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), palette["soft"]), ("BOX", (0, 0), (-1, -1), .5, palette["line"]), ("INNERGRID", (0, 0), (-1, -1), .5, palette["line"]), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))

    education_table = Table([[field("TRÌNH ĐỘ HỌC VẤN", profile.get("education") or getattr(candidate, "education_level", None)), field("KINH NGHIỆM", f"{profile.get('years_experience', 0):g} năm")], [field("CHUYÊN MÔN", getattr(candidate, "specialization", None)), field("NƠI ĐÀO TẠO", getattr(candidate, "training_institution", None))]], colWidths=[85 * mm, 85 * mm])
    education_table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), .5, palette["line"]), ("INNERGRID", (0, 0), (-1, -1), .5, palette["line"]), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))

    story = [header, *section("MỤC TIÊU NGHỀ NGHIỆP"), target_table, *section("GIỚI THIỆU"), Paragraph(safe(profile.get("summary"), "Chưa cập nhật phần giới thiệu."), styles["CVBody"]), *section("KỸ NĂNG"), Paragraph(safe(skills), styles["CVBody"]), *section("HỌC VẤN & KINH NGHIỆM"), education_table]
    if getattr(candidate, "foreign_language", None) or getattr(candidate, "computer_skill", None):
        story += [*section("NĂNG LỰC BỔ SUNG"), Paragraph(f"<b>Ngoại ngữ:</b> {safe(getattr(candidate, 'foreign_language', None))}<br/><b>Tin học:</b> {safe(getattr(candidate, 'computer_skill', None))}", styles["CVBody"])]
    stream = BytesIO()
    document = SimpleDocTemplate(stream, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm, title=f"CV - {user.full_name or 'Ung vien'}", author="Job4U")
    document.build(story)
    stream.seek(0)
    return StreamingResponse(stream, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=ho-so-so.pdf"})


@router.get("/privacy/consents")
async def get_consents(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Consent).where(Consent.user_id == user.id))).scalars().all()
    return rows


@router.put("/privacy/consents")
async def set_consent(payload: ConsentInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Purpose-specific consent: withdrawal only blocks future processing, not past logs."""
    from datetime import datetime, timezone
    consent = (await db.execute(select(Consent).where(Consent.user_id == user.id, Consent.purpose == payload.purpose))).scalar_one_or_none()
    if consent is None:
        consent = Consent(user_id=user.id, purpose=payload.purpose, consent_text_version=payload.consent_text_version)
        db.add(consent)
    consent.consent_text_version = payload.consent_text_version
    if payload.granted:
        consent.granted_at, consent.revoked_at = datetime.now(timezone.utc), None
    else:
        consent.revoked_at = datetime.now(timezone.utc)
    return {"purpose": payload.purpose, "granted": payload.granted}


@router.delete("/privacy/my-data")
async def erase_future_personal_data(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Fulfil an erasure request without deleting minimal historical share-consent evidence."""
    await db.execute(text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": str(user.id)})
    documents = (await db.execute(select(Document).where(Document.user_id == user.id))).scalars().all()
    for item in documents:
        try:
            delete_document(item.file_path)
        except Exception:
            # A retryable storage outage must not make the account look erased; keep its DB row.
            raise HTTPException(503, "Chưa thể xóa file ở kho lưu trữ; vui lòng thử lại.")
        await db.delete(item)
    await db.execute(delete(DigitalProfile).where(DigitalProfile.user_id == user.id))
    rows = (await db.execute(select(Consent).where(Consent.user_id == user.id))).scalars().all()
    from datetime import datetime, timezone
    for row in rows: row.revoked_at = datetime.now(timezone.utc)
    user.is_active = False
    # ShareConsentLog deliberately stays minimal evidence of an already completed disclosure.
    return {"message": "Đã xóa hồ sơ số và giấy tờ; tài khoản đã được vô hiệu hóa."}
