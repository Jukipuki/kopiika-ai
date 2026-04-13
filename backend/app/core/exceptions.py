import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 401, details: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class RegistrationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ValidationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422, details: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ForbiddenError(Exception):
    def __init__(
        self,
        code: str = "ACCESS_DENIED",
        message: str = "You do not have permission to access this resource",
        status_code: int = 403,
        details: dict | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


async def authentication_error_handler(_request: Request, exc: AuthenticationError) -> JSONResponse:
    headers: dict[str, str] = {}
    if exc.code == "RATE_LIMITED" and "retryAfter" in exc.details:
        headers["Retry-After"] = str(exc.details["retryAfter"])
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        headers=headers or None,
    )


async def registration_error_handler(_request: Request, exc: RegistrationError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


async def validation_error_handler(_request: Request, exc: ValidationError) -> JSONResponse:
    suggestions = exc.details.get("suggestions") if exc.details else None
    details = {k: v for k, v in exc.details.items() if k != "suggestions"} if exc.details else {}
    error_body: dict = {"code": exc.code, "message": exc.message, "details": details}
    if suggestions is not None:
        error_body["suggestions"] = suggestions
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error_body},
    )


async def forbidden_error_handler(_request: Request, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "Something went wrong", "details": {}}},
    )


async def request_validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    fields: list[str] = []
    for err in exc.errors():
        loc = err.get("loc", ())
        field = ".".join(str(part) for part in loc if part != "body")
        if field:
            fields.append(field)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Please check your input and try again",
                "details": {"fields": fields},
            }
        },
    )
