import hashlib
import logging
import re

from jose import jwt as jose_jwt
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import engine
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

# Maps URL path prefix → resource_type for financial data endpoints
AUDIT_PATH_RESOURCE_MAP: dict[str, str] = {
    "/api/v1/users/me/data-summary": "user_data",  # must come before /users/me
    "/api/v1/users/me": "user",
    "/api/v1/transactions": "transactions",
    "/api/v1/insights": "insights",
    "/api/v1/profile": "profile",
    "/api/v1/health-score": "health_scores",
    "/api/v1/uploads": "uploads",
}

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _method_to_action(method: str) -> str:
    if method == "GET":
        return "read"
    if method == "DELETE":
        return "delete"
    return "write"


def _extract_resource_id(path: str) -> str | None:
    parts = path.rstrip("/").split("/")
    last = parts[-1] if parts else ""
    return last if _UUID_RE.match(last) else None


class AuditMiddleware(BaseHTTPMiddleware):
    """Transparently log all financial data access events for GDPR compliance."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)  # always call first

        # Skip OPTIONS preflight and failed/unauthenticated requests
        if request.method == "OPTIONS" or response.status_code >= 400:
            return response

        # Determine resource_type from path — longer prefix checked first to avoid
        # /users/me/data-summary matching /users/me
        resource_type = None
        for prefix, rtype in AUDIT_PATH_RESOURCE_MAP.items():
            if request.url.path.startswith(prefix):
                resource_type = rtype
                break

        if resource_type is None:
            return response  # non-financial path, skip audit

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return response  # no token, skip (unauthenticated request already rejected upstream)

        try:
            token = auth_header[7:]
            claims = jose_jwt.get_unverified_claims(token)
            cognito_sub = claims.get("sub", "unknown")

            resource_id = _extract_resource_id(request.url.path)
            action_type = _method_to_action(request.method)

            x_forwarded = request.headers.get("x-forwarded-for", "")
            ip = (
                x_forwarded.split(",")[0].strip()
                if x_forwarded
                else (request.client.host if request.client else "unknown")
            )
            user_agent = request.headers.get("user-agent", "")

            async with SQLModelAsyncSession(engine) as audit_session:
                entry = AuditLog(
                    user_id=cognito_sub,
                    action_type=action_type,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    ip_address=ip or None,
                    user_agent=user_agent or None,
                )
                audit_session.add(entry)
                await audit_session.commit()
        except Exception:
            logger.warning("audit_log_failed", exc_info=True)

        return response


async def anonymize_user_audit_records(
    session: SQLModelAsyncSession, cognito_sub: str
) -> None:
    """Replace cognito_sub with its SHA-256 hash in audit_logs before user deletion."""
    hashed = hashlib.sha256(cognito_sub.encode()).hexdigest()
    await session.exec(
        text("UPDATE audit_logs SET user_id = :hashed WHERE user_id = :sub").bindparams(
            hashed=hashed, sub=cognito_sub
        )
    )
