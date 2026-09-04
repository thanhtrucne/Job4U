"""Read-only environment preflight for the graduation-project demo."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from minio import Minio
from sqlalchemy import text
import urllib3

from backend.config import settings
from backend.database import engine


async def check_postgres() -> bool:
    try:
        async with engine.connect() as connection:
            database = (await connection.execute(text("SELECT current_database()"))).scalar_one()
        print(f"[OK] PostgreSQL: {database} (SSL required by application config)")
        return True
    except Exception as error:
        print(f"[FAIL] PostgreSQL: {type(error).__name__}: {error}")
        return False
    finally:
        await engine.dispose()


def check_minio() -> bool:
    try:
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            # Fail quickly in a demo preflight instead of retrying a stopped service.
            http_client=urllib3.PoolManager(timeout=urllib3.Timeout(connect=2, read=2), retries=False),
        )
        client.list_buckets()
        print(f"[OK] MinIO: {settings.MINIO_ENDPOINT}")
        return True
    except Exception as error:
        print(f"[FAIL] MinIO: {type(error).__name__}: {error}")
        return False


async def main() -> int:
    postgres_ok = await check_postgres()
    minio_ok = check_minio()
    return 0 if postgres_ok and minio_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
