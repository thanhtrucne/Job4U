from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user, require_roles
from backend.api.profiles import _require_active_consent
from backend.config import settings
from backend.database import get_db
from backend.models import Document, User
from backend.services.object_storage import presigned_download, upload_document

router = APIRouter(prefix="/documents", tags=["documents", "admin"])
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
SENSITIVE_TYPES = {"personal_profile", "health_certificate", "identity_card"}
ALLOWED_TYPES = {"personal_profile", "job_application", "health_certificate", "qualification", "identity_card"}


async def _set_rls_user(db: AsyncSession, user_id: int) -> None:
    # RLS reads a transaction-local value so pooled DB connections cannot leak identity.
    await db.execute(text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": str(user_id)})


@router.post("")
async def upload_wallet_document(doc_type: str = Form(...), expiry_date: date | None = Form(None), sensitive_metadata: str | None = Form(None), file: UploadFile = File(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _require_active_consent(db, user.id, "reuse_documents")
    if doc_type not in ALLOWED_TYPES or not file.filename:
        raise HTTPException(422, "Loại giấy tờ không hợp lệ.")
    if sensitive_metadata and (doc_type not in SENSITIVE_TYPES or not settings.DOCUMENT_ENCRYPTION_KEY):
        raise HTTPException(422, "Chỉ giấy tờ nhạy cảm mới có metadata mã hóa; cần cấu hình DOCUMENT_ENCRYPTION_KEY.")
    content = await file.read()
    if not content or len(content) > MAX_DOCUMENT_BYTES:
        raise HTTPException(413, "Tệp phải có dung lượng từ 1 byte đến 10 MB.")
    await _set_rls_user(db, user.id)
    object_key = upload_document(user.id, file.filename, content, file.content_type or "application/octet-stream")
    item = Document(user_id=user.id, doc_type=doc_type, file_path=object_key, is_sensitive=doc_type in SENSITIVE_TYPES, expiry_date=expiry_date)
    db.add(item); await db.flush()
    if sensitive_metadata:
        # pgcrypto encrypts the optional ID/health metadata at rest. No document file is read or OCRed.
        await db.execute(text("UPDATE documents SET sensitive_metadata_encrypted = encode(pgp_sym_encrypt(:value, :key), 'base64') WHERE id = :id"), {"value": sensitive_metadata, "key": settings.DOCUMENT_ENCRYPTION_KEY, "id": item.id})
    return {"id": item.id, "status": item.status, "is_sensitive": item.is_sensitive}


@router.get("")
async def my_documents(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _set_rls_user(db, user.id)
    rows = (await db.execute(select(Document).where(Document.user_id == user.id).order_by(Document.uploaded_at.desc()))).scalars().all()
    return rows


@router.get("/{document_id}/download")
async def document_download(document_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _set_rls_user(db, user.id)
    item = (await db.execute(select(Document).where(Document.id == document_id, Document.user_id == user.id))).scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Không tìm thấy giấy tờ.")
    return {"url": presigned_download(item.file_path), "expires_in_seconds": 600}


@router.get("/admin/pending")
async def pending_documents(_: User = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Document).where(Document.status == "pending").order_by(Document.uploaded_at))).scalars().all()


@router.get("/admin/{document_id}/download")
async def admin_document_download(document_id: int, _: User = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    item = (await db.execute(select(Document).where(Document.id == document_id))).scalar_one_or_none()
    if item is None: raise HTTPException(404, "Không tìm thấy giấy tờ.")
    return {"url": presigned_download(item.file_path), "expires_in_seconds": 600}


@router.put("/admin/{document_id}")
async def review_document(document_id: int, decision: str = Form(...), rejection_reason: str | None = Form(None), admin: User = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    if decision not in {"verified", "rejected"} or (decision == "rejected" and not rejection_reason):
        raise HTTPException(422, "Cần chọn verified/rejected; từ chối phải có lý do.")
    item = (await db.execute(select(Document).where(Document.id == document_id))).scalar_one_or_none()
    if item is None: raise HTTPException(404, "Không tìm thấy giấy tờ.")
    item.status, item.rejection_reason, item.verified_by, item.verified_at = decision, rejection_reason, admin.id, datetime.now(timezone.utc)
    return {"id": item.id, "status": item.status}


async def expire_documents(db: AsyncSession) -> int:
    """Called by scheduler; expiry is deterministic and does not inspect document content."""
    rows = (await db.execute(select(Document).where(Document.expiry_date < date.today(), Document.status.in_(["pending", "verified"])))).scalars().all()
    for item in rows: item.status = "expired"
    return len(rows)
