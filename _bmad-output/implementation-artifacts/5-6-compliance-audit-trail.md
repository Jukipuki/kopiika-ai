# Story 5.6: Compliance Audit Trail

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want all financial data access events logged with user ID, timestamp, action type, and resource for GDPR accountability,
So that the system maintains a compliance audit trail distinct from operational logging.

## Acceptance Criteria

1. **Given** any API request that accesses financial data (transactions, insights, profile, feedback, health scores), **When** the request is processed, **Then** a compliance audit log entry is recorded with: user_id, timestamp, action_type (read/write/delete), resource_type, resource_id, and request metadata (IP, user agent)

2. **Given** the audit trail middleware (`core/audit.py`), **When** it intercepts data access endpoints, **Then** it logs transparently without affecting request performance or response payload

3. **Given** a user exercises their right to data deletion (Story 5.5), **When** their data is deleted, **Then** the audit trail retains only anonymized records (user_id replaced with a hash, no personal data) for regulatory compliance

4. **Given** the audit log entries, **When** an operator queries them, **Then** they can filter by user_id, date range, action_type, and resource_type to reconstruct a complete data access history for any user

5. **Given** audit log storage, **When** entries are persisted, **Then** they are stored in a structured format (JSON) separate from operational logs, with a retention policy of 2 years minimum

## Tasks / Subtasks

- [x] Task 1: Create AuditLog model and Alembic migration (AC: #1, #4, #5)
  - [x] 1.1 Create `backend/app/models/audit_log.py` — SQLModel class `AuditLog` with fields: `id` (UUID PK), `user_id` (VARCHAR 64, NOT NULL, **no FK to users table**), `timestamp` (timestamptz, default now()), `action_type` (VARCHAR 10: 'read'/'write'/'delete'), `resource_type` (VARCHAR 50), `resource_id` (VARCHAR 255, nullable), `ip_address` (VARCHAR 45, nullable), `user_agent` (TEXT, nullable)
  - [x] 1.2 Create Alembic migration `backend/alembic/versions/o1p2q3r4s5t6_add_audit_logs_table.py` — `CREATE TABLE audit_logs (...)` with indexes on `(user_id)`, `(timestamp)`, `(action_type)`, `(resource_type)` for operator query filtering

- [x] Task 2: Create `backend/app/core/audit.py` — AuditMiddleware (AC: #1, #2, #3)
  - [x] 2.1 Define `AUDIT_PATH_RESOURCE_MAP: dict[str, str]` — maps URL path prefix → resource_type:
    - `"/api/v1/transactions"` → `"transactions"`
    - `"/api/v1/insights"` → `"insights"`
    - `"/api/v1/profile"` → `"profile"`
    - `"/api/v1/health-score"` → `"health_scores"`
    - `"/api/v1/uploads"` → `"uploads"`
    - `"/api/v1/users/me/data-summary"` → `"user_data"`
    - `"/api/v1/users/me"` → `"user"` (covers DELETE /users/me from account.py)
  - [x] 2.2 Define `_method_to_action(method: str) -> str` — GET→'read', POST/PUT/PATCH→'write', DELETE→'delete'; defaults to 'read'
  - [x] 2.3 Define `_extract_resource_id(path: str) → str | None` — extracts last path segment if it looks like a UUID (matches UUID4 regex), else `None`
  - [x] 2.4 Implement `AuditMiddleware(BaseHTTPMiddleware)`:
    - Skip if no path matches AUDIT_PATH_RESOURCE_MAP prefix (early return via `call_next`)
    - Skip OPTIONS preflight
    - Call `await call_next(request)` — ALWAYS call first, then audit
    - Only log if `response.status_code < 400` (don't create audit records for failed/unauthenticated requests)
    - Extract `sub` (cognito_sub) from `Authorization: Bearer <token>` header using `jose.jwt.get_unverified_claims(token).get("sub", "unknown")` — **no JWKS fetch, no network call**, just decode payload bytes (this is a known-format Cognito JWT)
    - If no Authorization header: skip logging (unauthenticated request already rejected upstream)
    - IP: check `request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()`
    - User-Agent: `request.headers.get("user-agent", "")`
    - Write audit record via a fresh `SQLModelAsyncSession(engine)` context manager (independent of the request session)
    - **Wrap entire audit write in `try/except Exception`** — audit logging must NEVER raise or affect the response
  - [x] 2.5 Implement `anonymize_user_audit_records(session: SQLModelAsyncSession, cognito_sub: str) -> None` — async function that hashes cognito_sub using SHA-256 (hex digest), then executes `UPDATE audit_logs SET user_id = '<sha256_hash>' WHERE user_id = '<cognito_sub>'` via `sqlalchemy.text()`

- [x] Task 3: Register AuditMiddleware in `main.py` (AC: #2)
  - [x] 3.1 Import `AuditMiddleware` from `app.core.audit`
  - [x] 3.2 Add `app.add_middleware(AuditMiddleware)` — place AFTER `RequestLoggingMiddleware` registration (middleware executes in reverse registration order; audit runs before request logging in the stack, which is fine)

- [x] Task 4: Update `account_deletion_service.py` for audit anonymization (AC: #3)
  - [x] 4.1 Import `anonymize_user_audit_records` from `app.core.audit`
  - [x] 4.2 Call `await anonymize_user_audit_records(session, cognito_sub)` **before** the `await session.delete(user)` line — audit records must be updated within the same transaction before the user row is deleted
  - [x] 4.3 Update audit log entry in the deletion function: change the existing `logger.info("User data deleted", ...)` to also note audit anonymization: `extra={..., "audit_anonymized": True}`

- [x] Task 5: Backend tests (AC: #1, #2, #3, #4, #5)
  - [x] 5.1 Create `backend/tests/test_audit_middleware.py`
  - [x] 5.2 Test: GET `/api/v1/transactions` from authenticated user → audit_logs contains 1 entry with action_type='read', resource_type='transactions', valid user_id (cognito_sub), IP, user_agent
  - [x] 5.3 Test: POST `/api/v1/uploads` → audit_logs entry with action_type='write', resource_type='uploads'
  - [x] 5.4 Test: DELETE `/api/v1/users/me` → audit_logs entry with action_type='delete', resource_type='user'
  - [x] 5.5 Test: GET `/api/v1/health` (non-financial) → no audit_logs entry created
  - [x] 5.6 Test: unauthenticated request (no Bearer token) → no audit_logs entry created
  - [x] 5.7 Test `anonymize_user_audit_records`: pre-insert 2 audit records with cognito_sub as user_id, call function, verify both records now have sha256(cognito_sub) as user_id and original user_id is gone
  - [x] 5.8 Test: after anonymization (simulating account deletion), audit records survive in DB but with hashed user_id (NOT original cognito_sub)
  - [x] 5.9 Test: audit records for OTHER users are unaffected by anonymization of user A

- [x] Task 6: Full regression (all ACs)
  - [x] 6.1 Run `cd backend && python -m pytest` — 489 tests passed, 0 regressions

## Dev Notes

### Architecture Decisions

- **`audit_logs` has NO FK to `users` table** — this is intentional. When a user is deleted (Story 5.5 cascades), audit records must survive for GDPR accountability. The lack of FK is the mechanism that ensures survival. Instead, the user_id column is VARCHAR(64) (stores cognito_sub initially, then SHA-256 hash post-anonymization).
- **Middleware vs. dependency injection**: Architecture doc (`planning-artifacts/architecture.md:1160`) specifies `audit.py` as a middleware. Starlette `BaseHTTPMiddleware` is used (same pattern as `RequestLoggingMiddleware` in `core/middleware.py`). This requires zero changes to existing endpoints — fully transparent.
- **cognito_sub as user_id in audit_logs**: Middleware cannot efficiently do a DB lookup (cognito_sub → internal UUID) for every audited request without adding latency. Cognito `sub` is a stable, unique UUID-like string that serves the same compliance purpose. The anonymization step in account_deletion_service hashes this value.
- **`jose.jwt.get_unverified_claims()`**: We use unverified decoding in the audit middleware (no JWKS fetch, no network call, no latency). This is acceptable because: (a) the actual authentication check is already performed by the FastAPI endpoint's `get_current_user_id` dependency, (b) if the token was invalid/tampered, the endpoint would return 401 and the middleware skips logging for 4xx responses, (c) performance of audit logging must not degrade request latency.
- **Fresh DB session in middleware**: The audit write uses `async with SQLModelAsyncSession(engine) as audit_session:` independent of the request's DB session. This isolates audit writes from the request transaction — audit records are committed even if the request transaction rolls back. See `core/database.py:engine` for the async engine.
- **Retention policy**: The 2-year minimum retention is enforced at the infrastructure level (CloudWatch log group retention for structured logs + no automated DB cleanup for `audit_logs`). No application-level deletion of audit records — they're permanent until regulatory requirements expire.

### Endpoint Coverage

Financial data endpoints audited (path prefix matching):

| Endpoint | resource_type | Relevant router file |
|----------|---------------|---------------------|
| GET/POST `/api/v1/transactions*` | `transactions` | `api/v1/transactions.py` |
| GET `/api/v1/insights*` | `insights` | `api/v1/insights.py` |
| GET/PUT `/api/v1/profile*` | `profile` | `api/v1/profile.py` |
| GET `/api/v1/health-score*` | `health_scores` | `api/v1/health_score.py` |
| GET/POST `/api/v1/uploads*` | `uploads` | `api/v1/uploads.py` |
| GET `/api/v1/users/me/data-summary` | `user_data` | `api/v1/data_summary.py` |
| DELETE `/api/v1/users/me` | `user` | `api/v1/account.py` |

Note: `/api/v1/auth`, `/api/v1/consent`, `/api/v1/jobs` are NOT audited (auth events, consent records, and job status are operational, not financial data access).

### AuditLog Model Structure

```python
# backend/app/models/audit_log.py
import hashlib
import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: str = Field(max_length=64, index=True)          # cognito_sub or its sha256 hash post-anonymization
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    action_type: str = Field(max_length=10)                   # 'read', 'write', 'delete'
    resource_type: str = Field(max_length=50, index=True)     # 'transactions', 'insights', etc.
    resource_id: Optional[str] = Field(default=None, max_length=255)  # UUID path param if present
    ip_address: Optional[str] = Field(default=None, max_length=45)    # IPv4 or IPv6
    user_agent: Optional[str] = Field(default=None)           # Full UA string
```

### AuditMiddleware Skeleton

```python
# backend/app/core/audit.py
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

AUDIT_PATH_RESOURCE_MAP = {
    "/api/v1/transactions": "transactions",
    "/api/v1/insights": "insights",
    "/api/v1/profile": "profile",
    "/api/v1/health-score": "health_scores",
    "/api/v1/uploads": "uploads",
    "/api/v1/users/me/data-summary": "user_data",
    "/api/v1/users/me": "user",
}

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)  # always call first

        if request.method == "OPTIONS" or response.status_code >= 400:
            return response

        resource_type = None
        for prefix, rtype in AUDIT_PATH_RESOURCE_MAP.items():
            if request.url.path.startswith(prefix):
                resource_type = rtype
                break

        if resource_type is None:
            return response  # non-financial path, skip audit

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return response  # no token, skip

        try:
            token = auth_header[7:]
            claims = jose_jwt.get_unverified_claims(token)
            cognito_sub = claims.get("sub", "unknown")

            parts = request.url.path.rstrip("/").split("/")
            resource_id = parts[-1] if parts and _UUID_RE.match(parts[-1]) else None

            action_type = {"GET": "read", "DELETE": "delete"}.get(request.method, "write")

            ip = (request.headers.get("x-forwarded-for", "") or
                  (request.client.host if request.client else "unknown")).split(",")[0].strip()
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
        text("UPDATE audit_logs SET user_id = :hashed WHERE user_id = :sub"),
        {"hashed": hashed, "sub": cognito_sub},
    )
```

### account_deletion_service.py Integration

The existing `delete_all_user_data(session, user_id, cognito_sub, s3_keys)` in `backend/app/services/account_deletion_service.py` needs one new step — insert `await anonymize_user_audit_records(session, cognito_sub)` **before** `await session.delete(user)`. Both run in the same session/transaction so the anonymization and cascade delete are atomic.

### Previous Story Intelligence (5.5)

- `account_deletion_service.py` already handles S3, DB cascade, Cognito deletion
- The `delete_all_user_data` function signature: `(session, user_id, cognito_sub, s3_keys)` — has `cognito_sub` so anonymization can be passed directly
- `DELETE /api/v1/users/me` endpoint returns HTTP 204
- Test patterns: `backend/tests/test_account_deletion_api.py` — async pytest with dependency overrides, `AsyncClient`; mock boto3 S3 client and CognitoService via `app.dependency_overrides`
- `conftest.py` provides `async_client`, `db_session`, `test_user` fixtures

### Testing Patterns

- **Audit middleware tests**: Use `AsyncClient(app=app, base_url="http://test")` with `override_dependencies`
- **Counting audit records**: `from sqlmodel import select; count = (await session.exec(select(AuditLog))).all()`
- **No mocking of AuditMiddleware itself** — test that it actually writes records to the test DB
- **Anonymization unit test**: insert `AuditLog(user_id=cognito_sub, ...)` directly, call `anonymize_user_audit_records`, assert `user_id == hashlib.sha256(cognito_sub.encode()).hexdigest()`

### Git Intelligence

- Recent commits: `Story 3.9: Key Metric Prompt Refinement`, `Story 2.9: Expand CURRENCY_MAP`, `Story 2.8: Upload Completion UX & Summary`
- This is a **backend-only story** — no frontend changes
- Commit message pattern: `Story X.Y: Title` (e.g. "Story 5.6: Compliance Audit Trail")

### Project Structure Notes

- New files follow established conventions:
  - `backend/app/models/audit_log.py` → alongside `user.py`, `transaction.py` etc.
  - `backend/app/core/audit.py` → alongside `middleware.py`, `logging.py`
  - `backend/alembic/versions/<hash>_add_audit_logs_table.py` → standard Alembic naming
  - `backend/tests/test_audit_middleware.py` → alongside `test_account_deletion_api.py`
- `main.py` is the only existing file modified (plus `account_deletion_service.py`)
- No frontend changes — this is purely backend compliance infrastructure

### Key Risk: BaseHTTPMiddleware Response Streaming

`BaseHTTPMiddleware` can interfere with streaming responses (SSE). The existing `RequestLoggingMiddleware` already handles this without issues for SSE endpoints. Our `AuditMiddleware` follows the same pattern and calls `call_next()` first — but be aware that if SSE endpoints are audited (they're not in our path map, since SSE goes through `/api/v1/jobs`), streaming would need special handling. Confirmed: `/api/v1/jobs` is excluded from audit paths, so no SSE interference risk.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 5, Story 5.6, lines 1311–1338]
- [Source: _bmad-output/planning-artifacts/architecture.md:123 — Compliance Audit Trail architecture decision]
- [Source: _bmad-output/planning-artifacts/architecture.md:1160 — `core/audit.py` in project structure]
- [Source: backend/app/core/middleware.py — BaseHTTPMiddleware pattern]
- [Source: backend/app/core/logging.py — structured JSON logging]
- [Source: backend/app/core/security.py — jose.jwt usage, verify_token]
- [Source: backend/app/core/database.py — engine, get_session, async session pattern]
- [Source: backend/app/services/account_deletion_service.py — deletion flow, cognito_sub param]
- [Source: backend/app/main.py — middleware registration]
- [Source: _bmad-output/implementation-artifacts/5-5-delete-all-my-data.md — Previous story patterns, test approaches]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

None — implementation was straightforward. One note: used `session.exec(text(...).bindparams(...))` instead of `session.execute()` to avoid SQLModel's deprecation warning on raw SQL UPDATE in `anonymize_user_audit_records`.

### Completion Notes List

- Created `AuditLog` SQLModel (no FK to users, stores cognito_sub or its SHA-256 post-anonymization)
- Created Alembic migration `o1p2q3r4s5t6` with 4 indexes for operator query filtering
- Implemented `AuditMiddleware(BaseHTTPMiddleware)` — transparent, fires after `call_next`, skips 4xx and non-financial paths, uses fresh independent DB session per audit write wrapped in try/except
- Ordered `AUDIT_PATH_RESOURCE_MAP` so `/users/me/data-summary` is checked before `/users/me` (longer prefix first)
- Registered `AuditMiddleware` in `main.py` after `RequestLoggingMiddleware`
- Added `anonymize_user_audit_records()` call in `account_deletion_service.delete_all_user_data()` before user row deletion — runs in the same session/transaction so anonymization and cascade delete are atomic
- 8 new tests in `test_audit_middleware.py`; all 489 tests pass (zero regressions)
- Version bumped from 1.5.0 → 1.6.0 (MINOR: new infrastructure feature)

### File List

- backend/app/models/audit_log.py (new)
- backend/app/models/__init__.py (modified)
- backend/alembic/versions/o1p2q3r4s5t6_add_audit_logs_table.py (new)
- backend/app/core/audit.py (new)
- backend/app/main.py (modified)
- backend/app/services/account_deletion_service.py (modified)
- backend/tests/test_audit_middleware.py (new)
- backend/tests/test_account_deletion_api.py (modified — code-review integration test for audit anonymization)
- docs/operator-runbook.md (modified — code-review AC4 query interface)
- docs/tech-debt.md (modified — TD-013/TD-014/TD-015 promoted from code review)
- VERSION (modified)

## Change Log

- 2026-04-16: Story 5.6 implemented — AuditLog model, migration, AuditMiddleware, anonymization hook in account_deletion_service, 8 tests. All 489 tests pass.
- 2026-04-16: Version bumped from 1.5.0 → 1.6.0 per story completion.
- 2026-04-16: Code review applied — fixed migration tz mismatch (M5), loosened UUID regex (L1), capped `user_agent` length (L3), added operator-runbook audit-query section for AC4 (M1), added end-to-end deletion/anonymization integration test (M3). Three items deferred to tech-debt register: [TD-013](../../docs/tech-debt.md) (log failed access attempts — needs `status_code` column migration), [TD-014](../../docs/tech-debt.md) (2-year retention policy enforcement — infra/IaC scope), [TD-015](../../docs/tech-debt.md) (real-app middleware integration test — test-infra refactor). 490 backend tests pass.

## Code Review

**Reviewer:** Claude Opus 4.6 (adversarial code-review workflow)
**Date:** 2026-04-16

### Fixed in this PR

| ID | Severity | Summary | Fix |
|----|----------|---------|-----|
| M1 | MEDIUM | AC4 ("operator queries them") had no documented query interface | Added a new **Compliance Audit Log Queries** section to [docs/operator-runbook.md](../../docs/operator-runbook.md) covering all four AC-mandated filter dimensions (user_id, date range, action_type, resource_type) plus combined queries and volume stats |
| M3 | MEDIUM | `delete_all_user_data` → `anonymize_user_audit_records` wiring was untested end-to-end | Added `test_deletion_anonymizes_audit_records` in [test_account_deletion_api.py](../../backend/tests/test_account_deletion_api.py) — seeds audit rows for the deleted user + one unrelated user, calls `DELETE /users/me`, asserts hashing and cross-user isolation |
| M5 | MEDIUM | Migration used `sa.DateTime(timezone=True)` but `_utcnow()` strips tzinfo → naive datetime into a TIMESTAMPTZ column; tests only passed because SQLite ignores `timezone=True` | Changed migration to `sa.DateTime()` to match the codebase-wide convention used by all 11 other models |
| L1 | LOW | `_UUID_RE` only matched UUIDv4 (brittle if UUIDv7 is ever introduced) | Loosened to the generic `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$` shape |
| L3 | LOW | `user_agent` had no length cap (storage bloat from long bot UAs) | Added `max_length=500` on the model and `length=500` on the `AutoString` in the migration |

### Deferred to tech-debt register

| Finding | TD ID | Severity | Why deferred |
|---------|-------|----------|--------------|
| Middleware skips `>= 400` responses, so failed/unauthorized access attempts never appear in the audit trail | [TD-013](../../docs/tech-debt.md) | HIGH | Proper fix needs a new `status_code` column (another migration) + a design call on `401` attribution. AC1 is technically satisfied under the reading "requests that access data" = successes, so this is a compliance enhancement rather than a story-blocking gap |
| "2-year retention policy" is documented in Dev Notes but has no IaC / CloudWatch / cleanup job / test anywhere | [TD-014](../../docs/tech-debt.md) | MEDIUM | Infrastructure story — Terraform or AWS Console work plus a runbook entry. Out of scope for an application-level audit-trail story |
| Middleware tests use a fabricated `stub_app` rather than the real FastAPI `app`, so real-middleware-ordering and real-auth-dep regressions are not guarded | [TD-015](../../docs/tech-debt.md) | MEDIUM | Test-infra refactor (new `audit_real_client` fixture in `conftest.py`). The new M3 integration test covers the most critical path (deletion/anonymization) via the real app |

### Dropped on review

- Sub-resource path UUID extraction (no such routes exist today — speculative).
- Raw `text()` UPDATE vs. `update()` builder (cosmetic; parameters are bound, no injection risk).
- Async fire-and-forget audit writes (premature optimization at current traffic).
- Story dev-note wording about middleware order ("audit runs before request logging in the stack") is technically inverted, but the actual placement is fine — noted here for future readers, no change needed.

### Verification

- [x] `backend && pytest tests/test_audit_middleware.py tests/test_account_deletion_api.py -v` → 14/14 pass
- [x] `backend && pytest` (full suite) → 490 passed, 2 warnings, 0 failures, 163s
- [x] Git File List matches actual changes (plus this review adds entries for the operator-runbook and account-deletion test edits)
