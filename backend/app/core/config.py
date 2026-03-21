from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Kopiika AI"
    VERSION: str = "0.1.0"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/kopiika_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
