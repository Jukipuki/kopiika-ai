"""Shared request-parsing utilities."""

from __future__ import annotations

from fastapi import Request


def get_client_ip(request: Request) -> str | None:
    """Extract the originating client IP from the request.

    Checks ``X-Forwarded-For`` first (first hop), then falls back to
    ``request.client.host``. Returns ``None`` when neither is available.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None
