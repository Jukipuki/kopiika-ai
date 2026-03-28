import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Kopiika AI"
    VERSION: str = "0.1.0"

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
