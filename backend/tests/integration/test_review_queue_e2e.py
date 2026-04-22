"""End-to-end review-queue test (Story 11.8 AC #13).

Exercises the full Stage D pipeline end-to-end with canned LLM responses:
  1. Build three transactions that land at each confidence tier (auto, soft, queue).
  2. Run the categorization node with a stub LLM — it assigns the confidences.
  3. Simulate the persist loop (``_maybe_build_review_queue_entry``) to write
     transactions + queue rows into SQLite.
  4. Call the three API endpoints over HTTP:
       GET    /api/v1/transactions/review-queue   → 1 entry (the queue-tier row)
       POST   /{id}/resolve                       → transaction + queue updated
       POST   /{id}/dismiss                       → queue dismissed, txn unchanged

Marker-gated so CI can skip when running a fast-feedback slice.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

import app.models  # noqa: F401
from app.agents.categorization.node import categorization_node
from app.models.transaction import Transaction
from app.models.uncategorized_review_queue import UncategorizedReviewQueue
from app.models.upload import Upload
from app.models.user import User
from app.tasks.processing_tasks import _maybe_build_review_queue_entry


pytestmark = pytest.mark.integration


class _StubLLM:
    model_name = "stub"
    model = "stub"

    def __init__(self, responses: dict[str, dict]):
        self._responses = responses

    def invoke(self, prompt: str):
        items = [
            {
                "id": tid,
                "category": r["category"],
                "transaction_kind": r["transaction_kind"],
                "confidence": r["confidence"],
            }
            for tid, r in self._responses.items()
        ]
        return SimpleNamespace(
            content=json.dumps(items),
            usage_metadata={"total_tokens": 0},
        )


@pytest_asyncio.fixture
async def rq_engine():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()
    os.unlink(db_path)


@pytest_asyncio.fixture
async def rq_client(rq_engine):
    from app.api.deps import get_cognito_service, get_db, get_rate_limiter
    from app.main import app

    async def override_get_db():
        async with SQLModelAsyncSession(rq_engine) as session:
            yield session

    mock_rate = AsyncMock()
    mock_rate.check_rate_limit.return_value = None
    mock_rate.check_upload_rate_limit.return_value = None
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cognito_service] = lambda: MagicMock()
    app.dependency_overrides[get_rate_limiter] = lambda: mock_rate

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _auth_override(cognito_sub: str):
    async def _payload():
        return {"sub": cognito_sub}
    return _payload


async def _seed_empty_user(session: SQLModelAsyncSession, cognito_sub: str):
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    session.add(User(id=user_id, email=f"{uuid.uuid4()}@e.co", cognito_sub=cognito_sub))
    await session.flush()
    session.add(Upload(id=upload_id, user_id=user_id, file_name="t.csv", s3_key=f"{user_id}/t.csv", file_size=1, mime_type="text/csv"))
    await session.commit()
    return user_id, upload_id


@pytest.mark.asyncio
async def test_review_queue_full_flow(rq_client, rq_engine):
    from app.core.security import get_current_user_payload
    from app.main import app

    sub = f"sub-{uuid.uuid4()}"

    # --- Seed user / upload + build three canned LLM responses ---------------
    async with SQLModelAsyncSession(rq_engine) as s:
        user_id, upload_id = await _seed_empty_user(s, sub)

    canned = {
        "t-auto":  {"category": "restaurants", "transaction_kind": "spending", "confidence": 0.95},
        "t-soft":  {"category": "shopping",    "transaction_kind": "spending", "confidence": 0.72},
        "t-queue": {"category": "shopping",    "transaction_kind": "spending", "confidence": 0.40},
    }
    stub = _StubLLM(canned)

    txns_dict = [
        {"id": tid, "description": f"desc-{tid}", "amount": -5000, "mcc": None}
        for tid in canned
    ]

    state = {
        "job_id": "e2e-rq",
        "user_id": str(user_id),
        "upload_id": str(upload_id),
        "transactions": txns_dict,
        "completed_nodes": [],
    }

    with patch("app.agents.categorization.node.get_llm_client", return_value=stub):
        result_state = categorization_node(state)

    by_id = {r["transaction_id"]: r for r in result_state["categorized_transactions"]}

    # Tier assertions on pipeline output ---------------------------------------
    assert by_id["t-auto"]["flagged"] is False
    assert by_id["t-auto"]["category"] == "restaurants"
    assert by_id["t-soft"]["flagged"] is False
    assert by_id["t-soft"]["category"] == "shopping"
    assert by_id["t-queue"]["flagged"] is True
    assert by_id["t-queue"]["category"] == "uncategorized"
    assert by_id["t-queue"]["suggested_category"] == "shopping"

    # --- Simulate the persist loop -------------------------------------------
    async with SQLModelAsyncSession(rq_engine) as s:
        pipeline_tid_to_db_id: dict[str, uuid.UUID] = {}
        for txn_dict in txns_dict:
            cat = by_id[txn_dict["id"]]
            db_id = uuid.uuid4()
            pipeline_tid_to_db_id[txn_dict["id"]] = db_id
            row = Transaction(
                id=db_id,
                user_id=user_id,
                upload_id=upload_id,
                date=datetime(2026, 4, 22),
                description=txn_dict["description"],
                amount=txn_dict["amount"],
                currency_code=980,
                dedup_hash=uuid.uuid4().hex,
                category=cat["category"],
                transaction_kind=cat.get("transaction_kind", "spending"),
                confidence_score=cat["confidence_score"],
                is_flagged_for_review=cat.get("flagged", False),
                uncategorized_reason=cat.get("uncategorized_reason"),
            )
            s.add(row)
            await s.flush()
            entry = _maybe_build_review_queue_entry(cat=cat, txn=row)
            if entry is not None:
                s.add(entry)
        await s.commit()

        # Queue row count
        from sqlmodel import select
        queue_rows = (await s.exec(select(UncategorizedReviewQueue))).all()
        assert len(queue_rows) == 1
        assert queue_rows[0].transaction_id == pipeline_tid_to_db_id["t-queue"]
        assert queue_rows[0].suggested_category == "shopping"

    # --- Exercise the API over HTTP ------------------------------------------
    app.dependency_overrides[get_current_user_payload] = _auth_override(sub)
    try:
        # List → one pending entry
        resp = await rq_client.get("/api/v1/transactions/review-queue")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 1
        entry_id = body["items"][0]["id"]

        # Count
        resp_count = await rq_client.get("/api/v1/transactions/review-queue/count")
        assert resp_count.status_code == 200
        assert resp_count.json() == {"count": 1}

        # Resolve the queue entry → transaction should be updated
        resp_resolve = await rq_client.post(
            f"/api/v1/transactions/review-queue/{entry_id}/resolve",
            json={"category": "groceries", "kind": "spending"},
        )
        assert resp_resolve.status_code == 200, resp_resolve.text
        assert resp_resolve.json()["status"] == "resolved"

        # Count is now zero.
        resp_count2 = await rq_client.get("/api/v1/transactions/review-queue/count")
        assert resp_count2.json() == {"count": 0}
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)

    # DB state post-resolve: transaction stamped with user correction.
    async with SQLModelAsyncSession(rq_engine) as s:
        txn = await s.get(Transaction, pipeline_tid_to_db_id["t-queue"])
        assert txn.category == "groceries"
        assert txn.transaction_kind == "spending"
        assert txn.is_flagged_for_review is False
        assert txn.confidence_score == 1.0
        assert txn.uncategorized_reason is None


@pytest.mark.asyncio
async def test_review_queue_dismiss_leaves_transaction_unchanged(rq_client, rq_engine):
    from app.core.security import get_current_user_payload
    from app.main import app

    sub = f"sub-{uuid.uuid4()}"
    async with SQLModelAsyncSession(rq_engine) as s:
        user_id, upload_id = await _seed_empty_user(s, sub)
        txn_id = uuid.uuid4()
        entry_id = uuid.uuid4()
        s.add(Transaction(
            id=txn_id, user_id=user_id, upload_id=upload_id,
            date=datetime(2026, 4, 22), description="?", amount=-1000,
            currency_code=980, dedup_hash=uuid.uuid4().hex,
            category="uncategorized", transaction_kind="spending",
            confidence_score=0.4, is_flagged_for_review=True,
            uncategorized_reason="low_confidence",
        ))
        s.add(UncategorizedReviewQueue(
            id=entry_id, user_id=user_id, transaction_id=txn_id,
            categorization_confidence=0.4, suggested_category="shopping",
            suggested_kind="spending", status="pending",
        ))
        await s.commit()

    app.dependency_overrides[get_current_user_payload] = _auth_override(sub)
    try:
        resp = await rq_client.post(
            f"/api/v1/transactions/review-queue/{entry_id}/dismiss",
            json={"reason": "not actionable"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "dismissed"
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)

    async with SQLModelAsyncSession(rq_engine) as s:
        txn = await s.get(Transaction, txn_id)
        # Transaction stays flagged.
        assert txn.category == "uncategorized"
        assert txn.is_flagged_for_review is True
        assert txn.uncategorized_reason == "low_confidence"
