import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with timing, method, path, and a unique request ID."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Skip health endpoint and CORS preflight to avoid noise
        if path == "/health" or request.method == "OPTIONS":
            return await call_next(request)

        request_id = str(uuid.uuid4())
        start_time = time.monotonic()

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start_time) * 1000)

        logger.info(
            "http_request",
            extra={
                "method": request.method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "request_id": request_id,
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response
