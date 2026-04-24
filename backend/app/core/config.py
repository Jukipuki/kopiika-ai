import os
from typing import ClassVar, Literal, Optional

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
    LLM_PROVIDER: Literal["anthropic", "openai", "bedrock"] = "anthropic"
    # Story 11.8 three-tier thresholds (replaces single CATEGORIZATION_CONFIDENCE_THRESHOLD):
    #   confidence >= AUTO_APPLY      → silently accept LLM suggestion
    #   SOFT_FLAG <= confidence < AUTO_APPLY → accept LLM suggestion, emit telemetry
    #   confidence < SOFT_FLAG        → route to uncategorized_review_queue
    CATEGORIZATION_SOFT_FLAG_THRESHOLD: float = 0.6
    CATEGORIZATION_AUTO_APPLY_THRESHOLD: float = 0.85
    CATEGORIZATION_BATCH_SIZE: int = 50

    # Deployment environment (local | dev | staging | prod). Gates the local-only
    # Fernet fallback in app.core.crypto — non-local ENV must use KMS.
    ENV: str = "local"

    # KMS CMK ARN for IBAN envelope encryption (Story 11.10 / TD-049). Required
    # in non-local environments; local falls back to LOCAL_IBAN_FERNET_KEY.
    KMS_IBAN_KEY_ARN: Optional[str] = None

    # Local-dev-only Fernet key (urlsafe-b64, 32 bytes). NEVER set in staging/prod.
    LOCAL_IBAN_FERNET_KEY: Optional[str] = None

    # Chat runtime phasing — ADR-0004. "direct" = Phase A (bedrock-runtime
    # InvokeModel via llm.py). "agentcore" = Phase B (AgentCore container).
    CHAT_RUNTIME: Literal["direct", "agentcore"] = "direct"
    # Populated in Phase B; None in Phase A and in dev/staging.
    AGENTCORE_RUNTIME_ARN: Optional[str] = None
    # Bedrock Guardrail (Story 10.2). Attached to chat invocations by Story 10.5.
    BEDROCK_GUARDRAIL_ARN: Optional[str] = None
    # Memory bounds — architecture.md L1719: 20 turns or 8k tokens, whichever first.
    CHAT_SESSION_MAX_TURNS: int = 20
    CHAT_SESSION_MAX_TOKENS: int = 8000
    # Summarization keeps this many recent turns verbatim; older ones collapse
    # to a single role='system' summary message. Not env-overridable by design.
    CHAT_SUMMARIZATION_KEEP_RECENT_TURNS: int = 6

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
