"""MinIO adapter. Files are never stored in PostgreSQL and are never OCR processed."""
from io import BytesIO
from uuid import uuid4

from minio import Minio

from backend.config import settings


def _client() -> Minio:
    return Minio(settings.MINIO_ENDPOINT, access_key=settings.MINIO_ACCESS_KEY, secret_key=settings.MINIO_SECRET_KEY, secure=settings.MINIO_SECURE)


def upload_document(user_id: int, filename: str, content: bytes, content_type: str) -> str:
    client = _client()
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    object_key = f"users/{user_id}/{uuid4()}.{suffix}"
    client.put_object(settings.MINIO_BUCKET, object_key, BytesIO(content), len(content), content_type=content_type)
    return object_key

def upload_career_image(filename: str, content: bytes, content_type: str) -> str:
    client = _client()
    if not client.bucket_exists(settings.MINIO_BUCKET): client.make_bucket(settings.MINIO_BUCKET)
    suffix = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
    key = f"career-guides/{uuid4()}.{suffix}"
    client.put_object(settings.MINIO_BUCKET, key, BytesIO(content), len(content), content_type=content_type)
    return key

def read_career_image(filename: str) -> tuple[bytes, str | None]:
    response = _client().get_object(settings.MINIO_BUCKET, f"career-guides/{filename}")
    try: return response.read(), response.headers.get('Content-Type')
    finally: response.close(); response.release_conn()


def presigned_download(object_key: str) -> str:
    from datetime import timedelta
    return _client().presigned_get_object(settings.MINIO_BUCKET, object_key, expires=timedelta(minutes=10))


def delete_document(object_key: str) -> None:
    _client().remove_object(settings.MINIO_BUCKET, object_key)
