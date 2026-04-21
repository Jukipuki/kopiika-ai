import os
from typing import ClassVar, Optional

from pydantic_settings import BaseSettings

from app.core.version import APP_VERSION


class Settings(BaseSettings):
    PROJECT_NAME: str = "Kopiika AI"
    # ClassVar: keep VERSION out of the pydantic field set so a stray env var
    # named VERSION cannot silently override the file-backed source of truth.
    VERSION: ClassVar[str] = APP_VERSION

    # AWS Profile (set in OS env so boto3 picks it up)
    AWS_PROFILE: str = ""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/kopiika_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # AWS Cognito
    COGNITO_USER_POOL_ID: str = ""
    COGNITO_APP_CLIENT_ID: str = ""
    COGNITO_REGION: str = "eu-central-1"
    COGNITO_BACKEND_CLIENT_ID: str = ""
    COGNITO_BACKEND_CLIENT_SECRET: str = ""

    # S3
    S3_UPLOADS_BUCKET: str = ""
    S3_REGION: str = "eu-central-1"

    # LLM API Keys
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    CATEGORIZATION_CONFIDENCE_THRESHOLD: float = 0.7
    CATEGORIZATION_BATCH_SIZE: int = 50

    # Deployment environment (local | dev | staging | prod). Gates the local-only
    # Fernet fallback in app.core.crypto — non-local ENV must use KMS.
    ENV: str = "local"

    # KMS CMK ARN for IBAN envelope encryption (Story 11.10 / TD-049). Required
    # in non-local environments; local falls back to LOCAL_IBAN_FERNET_KEY.
    KMS_IBAN_KEY_ARN: Optional[str] = None

    # Local-dev-only Fernet key (urlsafe-b64, 32 bytes). NEVER set in staging/prod.
    LOCAL_IBAN_FERNET_KEY: Optional[str] = None

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Derive sync URL from async DATABASE_URL for Celery workers."""
        return self.DATABASE_URL.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        ).replace("sqlite+aiosqlite://", "sqlite://")


settings = Settings()

# Propagate AWS_PROFILE to OS environment so boto3 can see it
if settings.AWS_PROFILE:
    os.environ.setdefault("AWS_PROFILE", settings.AWS_PROFILE)
