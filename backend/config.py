import os
from pydantic import field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/topcv_db?ssl=require")
    DATABASE_URL_SYNC: str = os.getenv("DATABASE_URL_SYNC", "postgresql://postgres:password@localhost:5432/topcv_db?sslmode=require")

    # App
    APP_NAME: str = "TopCV Job Portal"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Admin
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey1234567890abcdef")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "Job4U")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    # Schema security (RLS/roles/pgcrypto) is installed only by the reviewed migration.
    AUTO_CREATE_TABLES: bool = os.getenv("AUTO_CREATE_TABLES", "false").lower() == "true"

    # MinIO runs as a separate binary/service; PostgreSQL stores only its object key.
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "job-portal-documents")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    DOCUMENT_ENCRYPTION_KEY: str = os.getenv("DOCUMENT_ENCRYPTION_KEY", "")

    # CORS
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000,http://127.0.0.1:3000",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # Crawler
    CRAWL_INTERVAL_MINUTES: int = int(os.getenv("CRAWL_INTERVAL_MINUTES", "30"))
    CRAWLER_DELAY_SECONDS: float = float(os.getenv("CRAWLER_DELAY_SECONDS", "2.0"))
    MAX_RETRY: int = int(os.getenv("MAX_RETRY", "3"))
    TOPCV_BASE_URL: str = "https://www.topcv.vn"

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    class Config:
        env_file = ".env"
        extra = "allow"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug(cls, value):
        # Existing deployments used DEBUG=release/development; keep them valid.
        if isinstance(value, str) and value.lower() in {"release", "production", "prod"}:
            return False
        if isinstance(value, str) and value.lower() in {"development", "dev"}:
            return True
        return value

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def require_async_ssl(cls, value: str) -> str:
        """Prevent an old .env value from silently disabling encrypted DB transport."""
        if "ssl=" not in value:
            value += "&ssl=require" if "?" in value else "?ssl=require"
        return value

    @field_validator("DATABASE_URL_SYNC", mode="after")
    @classmethod
    def require_sync_ssl(cls, value: str) -> str:
        if "sslmode=" not in value:
            value += "&sslmode=require" if "?" in value else "?sslmode=require"
        return value


settings = Settings()
