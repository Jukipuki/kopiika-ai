from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import v1_router
from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    RegistrationError,
    ValidationError,
    authentication_error_handler,
    registration_error_handler,
    validation_error_handler,
)

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Accept-Language"],
)

app.include_router(v1_router)

app.add_exception_handler(AuthenticationError, authentication_error_handler)
app.add_exception_handler(RegistrationError, registration_error_handler)
app.add_exception_handler(ValidationError, validation_error_handler)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "version": settings.VERSION}
