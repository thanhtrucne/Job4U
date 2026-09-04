"""Partner application flow with explicit, per-disclosure confirmation."""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user, require_roles
from backend.api.profiles import _require_active_consent
from backend.database import get_db
from backend.models import Application, ApplicationDocument, ApplicationFeedback, ApplicationShareRequest, CandidateProfile, Company, Consent, Document, Job, ShareConsentLog, User
from backend.models import DigitalProfile, ProfileSkill
from backend.services.object_storage import presigned_download, upload_document
from backend.services.email_service import send_application_feedback_email
from backend.schemas import ApplicationFeedbackInput

router = APIRouter(prefix="/applications", tags=["applications", "partner"])
MAX_APPLICATION_FILE_BYTES = 10 * 1024 * 1024
APPLICATION_FILE_TYPES = {
    ".pdf": {"application/pdf"},
    ".doc": {"application/msword", "application/octet-stream"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/octet-stream"},
    ".jpg": {"image/jpeg", "image/pjpeg"},
    ".jpeg": {"image/jpeg", "image/pjpeg"},
}


def _application_profile_data(profile: DigitalProfile | None, candidate: CandidateProfile | None, skills: list[ProfileSkill]) -> dict:
    """Combine the applicant's two profile forms into the job-facing fields.

    The account dashboard stores personal education, experience and address in
    ``candidate_profiles``.  The structured-CV form stores job preferences in
    ``digital_profiles``.  A recruiter who has been granted access to an
    application should see the populated value from either form, without
    exposing unrelated personal fields.
    """
    def value(profile_value, candidate_value=None):
        return profile_value if profile_value not in (None, "") else candidate_value

    desired_location = value(
        getattr(profile, "desired_location", None),
        ", ".join(part for part in (getattr(candidate, "province", None), getattr(candidate, "ward", None)) if part) or None,
    )
    return {
        "headline": value(getattr(profile, "headline", None), getattr(candidate, "specialization", None)),
        "industry": value(getattr(profile, "industry", None), getattr(candidate, "specialization", None)),
        # A newly created structured profile has a default of 0.  Prefer the
        # dashboard value when it records actual experience, so that default
        # does not hide information the applicant already entered.
        "years_experience": (
            getattr(profile, "years_experience", None)
            if getattr(profile, "years_experience", None) not in (None, 0)
            else getattr(candidate, "years_experience", None)
        ),
        "education": value(getattr(profile, "education", None), getattr(candidate, "education_level", None)),
        "desired_location": desired_location,
        "desired_job_level": getattr(profile, "desired_job_level", None),
        "desired_job_type": getattr(profile, "desired_job_type", None),
        "desired_salary_min": getattr(profile, "desired_salary_min", None),
        "desired_salary_max": getattr(profile, "desired_salary_max", None),
        "skill_ids": [item.skill_id for item in skills],
    }


SHAREABLE_WALLET_TYPES = {"health_certificate", "qualification", "personal_profile"}


async def _set_rls_user(db: AsyncSession, user_id: int) -> None:
    await db.execute(text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": str(user_id)})


def _validate_application_file(file: UploadFile, content: bytes) -> str:
    from pathlib import Path
    suffix = Path(file.filename or "").suffix.lower()
    if not file.filename or suffix not in APPLICATION_FILE_TYPES:
        raise HTTPException(422, "Chỉ hỗ trợ tệp PDF, Word (.doc/.docx) hoặc JPG/JPEG.")
    if not content or len(content) > MAX_APPLICATION_FILE_BYTES:
        raise HTTPException(413, "Tệp hồ sơ phải có dung lượng từ 1 byte đến 10 MB.")
    content_type = (file.content_type or "application/octet-stream").lower()
    if content_type not in APPLICATION_FILE_TYPES[suffix]:
        raise HTTPException(422, "Định dạng nội dung tệp không khớp với phần mở rộng.")
    return suffix


async def _documents_for_share(db: AsyncSession, application_id: int, user_id: int, requested_doc_types: list[str]) -> list[Document]:
    """Return only the documents authorized for this one application."""
    documents: list[Document] = []
    reusable_types = [item for item in requested_doc_types if item != "job_application"]
    if reusable_types:
        documents.extend((await db.execute(
            select(Document).where(
                Document.user_id == user_id,
                Document.doc_type.in_(reusable_types),
                Document.status == "verified",
            )
        )).scalars().all())
    if "job_application" in requested_doc_types:
        documents.extend((await db.execute(
            select(Document)
            .join(ApplicationDocument, ApplicationDocument.document_id == Document.id)
            .where(
                ApplicationDocument.application_id == application_id,
                Document.user_id == user_id,
                Document.doc_type == "job_application",
                Document.status == "verified",
            )
        )).scalars().all())
    return documents


@router.post("/jobs/{job_id}/submit")
async def submit_application(
    job_id: int,
    file: UploadFile = File(...),
    share_consent: bool = Form(...),
    additional_doc_types: str = Form("[]"),
    request: Request = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload one application file and address it to this job's company."""
    if not share_consent:
        raise HTTPException(422, "Bạn cần đồng ý gửi hồ sơ cho công ty trước khi nộp.")
    try:
        selected_types = list(dict.fromkeys(json.loads(additional_doc_types)))
    except (TypeError, json.JSONDecodeError):
        raise HTTPException(422, "Danh sách giấy tờ đính kèm không hợp lệ.")
    if not all(isinstance(item, str) and item in SHAREABLE_WALLET_TYPES for item in selected_types):
        raise HTTPException(422, "Chỉ được gửi Giấy khám sức khỏe, Bằng cấp/chứng chỉ hoặc Lý lịch cá nhân đã xác minh.")
    job = (await db.execute(select(Job).where(Job.id == job_id, Job.is_active.is_(True)))).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "Không tìm thấy việc làm.")
    company = (await db.execute(select(Company).where(Company.id == job.company_id))).scalar_one_or_none()
    if company is None:
        raise HTTPException(422, "Tin tuyển dụng chưa có thông tin công ty nhận hồ sơ.")
    existing = (await db.execute(
        select(Application).where(Application.user_id == user.id, Application.job_id == job.id)
    )).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(409, "Bạn đã ứng tuyển vị trí này.")
    content = await file.read()
    _validate_application_file(file, content)
    await _set_rls_user(db, user.id)

    application = Application(user_id=user.id, job_id=job.id, company_id=company.id)
    db.add(application)
    await db.flush()

    object_key = upload_document(user.id, file.filename, content, file.content_type or "application/octet-stream")
    # ``verified`` here means the file passed the portal's upload checks and is
    # ready for the selected partner; it does not assert the document's content.
    document = Document(user_id=user.id, doc_type="job_application", file_path=object_key, status="verified")
    db.add(document)
    await db.flush()
    db.add(ApplicationDocument(application_id=application.id, document_id=document.id))

    wallet_documents = (await db.execute(select(Document).where(
        Document.user_id == user.id,
        Document.doc_type.in_(selected_types),
        Document.status == "verified",
    ))).scalars().all() if selected_types else []
    if {str(item.doc_type) for item in wallet_documents} != set(selected_types):
        raise HTTPException(422, "Một hoặc nhiều giấy tờ đính kèm chưa được xác minh hoặc không còn hiệu lực.")

    consent = (await db.execute(select(Consent).where(Consent.user_id == user.id, Consent.purpose == "share_with_company"))).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if consent is None:
        consent = Consent(user_id=user.id, purpose="share_with_company", consent_text_version="2026.2")
        db.add(consent)
    consent.granted_at, consent.revoked_at, consent.consent_text_version = now, None, "2026.2"

    requested_types = ["job_application", *selected_types]
    share = ApplicationShareRequest(application_id=application.id, company_id=company.id, requested_doc_types=requested_types, status="granted")
    db.add(share)
    await db.flush()
    db.add(ShareConsentLog(
        share_request_id=share.id,
        user_id=user.id,
        data_shared_snapshot={"profile_user_id": user.id, "documents": [{"id": document.id, "type": "job_application", "status": "verified"}, *[{"id": item.id, "type": str(item.doc_type), "status": str(item.status)} for item in wallet_documents]]},
        ip_address=request.client.host if request and request.client else None,
    ))
    return {"application_id": application.id, "document_id": document.id, "recipient": company.name, "message": "Đã nộp hồ sơ cho công ty."}


@router.get("/jobs/{job_id}/status")
async def application_status(job_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Return only the signed-in applicant's submission status for one job."""
    application = (await db.execute(
        select(Application).where(Application.user_id == user.id, Application.job_id == job_id)
    )).scalar_one_or_none()
    if application is None:
        return {"applied": False}
    return {"applied": True, "application_id": application.id, "created_at": application.created_at, "status": application.status}


@router.post("/jobs/{job_id}")
async def start_application(job_id: int, requested_doc_types: list[str] = Body(default=[]), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(Job).where(Job.id == job_id, Job.is_active.is_(True)))).scalar_one_or_none()
    if job is None: raise HTTPException(404, "Không tìm thấy việc làm.")
    company = (await db.execute(select(Company).where(Company.id == job.company_id))).scalar_one_or_none()
    # A crawler listing stays outside the portal's personal-data boundary.
    if company is None or not company.is_partner:
        return {"mode": "redirect", "url": job.job_url, "message": "Ứng tuyển trên trang nguồn; hệ thống không gửi dữ liệu cá nhân của bạn."}
    documents = (await db.execute(select(Document).where(Document.user_id == user.id, Document.doc_type.in_(requested_doc_types), Document.status == "verified"))).scalars().all() if requested_doc_types else []
    available = {str(item.doc_type) for item in documents}
    missing = sorted(set(requested_doc_types) - available)
    if missing:
        return {"mode": "missing_documents", "missing_doc_types": missing}
    application = (await db.execute(select(Application).where(Application.user_id == user.id, Application.job_id == job.id))).scalar_one_or_none()
    if application is None:
        application = Application(user_id=user.id, job_id=job.id, company_id=company.id)
        db.add(application); await db.flush()
    share_request = ApplicationShareRequest(application_id=application.id, company_id=company.id, requested_doc_types=requested_doc_types)
    db.add(share_request); await db.flush()
    return {"mode": "confirm_share", "share_request_id": share_request.id, "recipient": company.name, "purpose": "Ứng tuyển vào vị trí đã chọn", "shared_document_types": requested_doc_types}


@router.post("/{share_request_id}/confirm")
async def confirm_sharing(share_request_id: int, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _require_active_consent(db, user.id, "share_with_company")
    share = (await db.execute(select(ApplicationShareRequest).where(ApplicationShareRequest.id == share_request_id))).scalar_one_or_none()
    if share is None or share.status != "pending": raise HTTPException(404, "Yêu cầu chia sẻ không hợp lệ.")
    application = (await db.execute(select(Application).where(Application.id == share.application_id, Application.user_id == user.id))).scalar_one_or_none()
    if application is None: raise HTTPException(403, "Bạn không sở hữu yêu cầu này.")
    docs = (await db.execute(select(Document).where(Document.user_id == user.id, Document.doc_type.in_(share.requested_doc_types), Document.status == "verified"))).scalars().all()
    if {str(item.doc_type) for item in docs} != set(share.requested_doc_types):
        raise HTTPException(422, "Một hoặc nhiều giấy tờ không còn được xác minh.")
    # Snapshot has only document IDs/types/statuses, never OCR text nor MinIO object keys.
    snapshot = {"profile_user_id": user.id, "documents": [{"id": item.id, "type": str(item.doc_type), "status": str(item.status)} for item in docs]}
    share.status = "granted"
    db.add(ShareConsentLog(share_request_id=share.id, user_id=user.id, data_shared_snapshot=snapshot, ip_address=request.client.host if request.client else None))
    return {"application_id": application.id, "status": "pending", "message": "Đã ghi nhận đồng ý và chia sẻ dữ liệu cho công ty đối tác."}


@router.get("/me")
async def my_applications(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Applicant-facing history; never exposes another applicant's data."""
    rows = (await db.execute(
        select(Application, Job, Company)
        .join(Job, Job.id == Application.job_id)
        .join(Company, Company.id == Application.company_id)
        .where(Application.user_id == user.id)
        .order_by(Application.created_at.desc())
    )).all()
    return [{
        "id": application.id,
        "status": application.status,
        "created_at": application.created_at,
        "job": {"id": job.id, "title": job.title, "location": job.location, "salary": job.salary},
        "company": {"name": company.name},
    } for application, job, company in rows]


@router.get("/me/feedback")
async def my_application_feedback(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Recruiter messages for the signed-in applicant only."""
    rows = (await db.execute(
        select(ApplicationFeedback, Job, Company)
        .join(Application, Application.id == ApplicationFeedback.application_id)
        .join(Job, Job.id == Application.job_id)
        .join(Company, Company.id == ApplicationFeedback.company_id)
        .where(ApplicationFeedback.recipient_user_id == user.id)
        .order_by(ApplicationFeedback.created_at.desc())
    )).all()
    for feedback, _, _ in rows:
        if feedback.read_at is None:
            feedback.read_at = datetime.now(timezone.utc)
    return [{
        "id": feedback.id, "application_id": feedback.application_id,
        "message": feedback.message, "created_at": feedback.created_at,
        "job_title": job.title, "company_name": company.name,
    } for feedback, job, company in rows]


@router.get("/partner/me")
async def partner_applications(user: User = Depends(require_roles("partner")), db: AsyncSession = Depends(get_db)):
    if not user.company_id: raise HTTPException(403, "Tài khoản partner chưa được gán công ty.")
    rows = (await db.execute(
        select(Application, Job)
        .join(Job, Job.id == Application.job_id)
        .where(Application.company_id == user.company_id)
        .order_by(Application.created_at.desc())
    )).all()
    return [{"id": application.id, "job_id": application.job_id, "job_title": job.title,
             "status": application.status, "created_at": application.created_at}
            for application, job in rows]


@router.get("/partner/{application_id}")
async def partner_application_detail(application_id: int, user: User = Depends(require_roles("partner")), db: AsyncSession = Depends(get_db)):
    """Only expose a profile while this partner's specific share request is granted."""
    row = (await db.execute(select(Application, User).join(User, User.id == Application.user_id).where(Application.id == application_id, Application.company_id == user.company_id))).one_or_none()
    if row is None:
        raise HTTPException(404, "Không tìm thấy hồ sơ ứng tuyển.")
    application, applicant = row
    share = (await db.execute(select(ApplicationShareRequest).where(ApplicationShareRequest.application_id == application.id, ApplicationShareRequest.company_id == user.company_id, ApplicationShareRequest.status == "granted"))).scalar_one_or_none()
    if share is None:
        raise HTTPException(403, "Ứng viên chưa cấp quyền hoặc quyền chia sẻ đã bị hủy.")
    # RLS is scoped to the applicant only after the partner's granted request was verified above.
    await db.execute(text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": str(application.user_id)})
    profile = (await db.execute(select(DigitalProfile).where(DigitalProfile.user_id == application.user_id))).scalar_one_or_none()
    candidate = (await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == application.user_id))).scalar_one_or_none()
    skills = (await db.execute(select(ProfileSkill).where(ProfileSkill.profile_id == profile.id))).scalars().all() if profile else []
    documents = await _documents_for_share(db, application.id, application.user_id, share.requested_doc_types)
    return {"application_id": application.id, "applicant": {"full_name": applicant.full_name, "email": applicant.email, "phone_number": applicant.phone_number}, "profile": _application_profile_data(profile, candidate, skills), "documents": [{"id": item.id, "doc_type": str(item.doc_type), "status": str(item.status)} for item in documents]}


@router.get("/partner/{application_id}/documents/{document_id}/download")
async def partner_document_download(application_id: int, document_id: int, user: User = Depends(require_roles("partner")), db: AsyncSession = Depends(get_db)):
    application = (await db.execute(select(Application).where(Application.id == application_id, Application.company_id == user.company_id))).scalar_one_or_none()
    share = (await db.execute(select(ApplicationShareRequest).where(ApplicationShareRequest.application_id == application_id, ApplicationShareRequest.company_id == user.company_id, ApplicationShareRequest.status == "granted"))).scalar_one_or_none()
    if application is None or share is None: raise HTTPException(403, "Không có quyền truy cập giấy tờ này.")
    await db.execute(text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": str(application.user_id)})
    item = next((document for document in await _documents_for_share(db, application.id, application.user_id, share.requested_doc_types) if document.id == document_id), None)
    if item is None: raise HTTPException(404, "Không tìm thấy giấy tờ được chia sẻ.")
    return {"url": presigned_download(item.file_path), "expires_in_seconds": 600}


@router.post("/partner/{application_id}/feedback")
async def send_application_feedback(application_id: int, payload: ApplicationFeedbackInput, background_tasks: BackgroundTasks, user: User = Depends(require_roles("partner")), db: AsyncSession = Depends(get_db)):
    """Send a written response; reviewing an application never changes its status."""
    row = (await db.execute(
        select(Application, User, Job, Company)
        .join(User, User.id == Application.user_id)
        .join(Job, Job.id == Application.job_id)
        .join(Company, Company.id == Application.company_id)
        .where(Application.id == application_id, Application.company_id == user.company_id)
    )).one_or_none()
    if row is None:
        raise HTTPException(404, "Không tìm thấy hồ sơ ứng tuyển.")
    application, applicant, job, company = row
    feedback = ApplicationFeedback(
        application_id=application.id, recipient_user_id=applicant.id,
        company_id=company.id, message=payload.message,
    )
    db.add(feedback)
    await db.flush()
    # Persist the in-app notification before scheduling optional email. This
    # keeps the applicant notification reliable even when SMTP is unavailable.
    feedback_id = feedback.id
    await db.commit()
    background_tasks.add_task(
        send_application_feedback_email, applicant.email, applicant.full_name or "bạn",
        company.name, job.title, feedback.message,
    )
    return {"id": feedback_id, "message": "Đã gửi phản hồi trong tài khoản ứng viên và qua email nếu SMTP đã được cấu hình."}
