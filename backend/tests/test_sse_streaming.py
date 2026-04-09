"""Tests for SSE streaming endpoint and Redis pub/sub utilities (Story 2.6)."""
import json
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from app.models.processing_job import ProcessingJob
from app.models.upload import Upload
from app.models.user import User


# ── Helper fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def sync_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


async def _create_user_job_async(session, status="processing", error_code=None, error_message=None, cognito_sub="sse-sub"):
    """Async helper to create user + upload + job. Returns (user_id, job_id)."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    job_id = uuid.uuid4()
    user = User(id=user_id, email=f"sse-{user_id}@test.com", cognito_sub=cognito_sub, locale="en")
    session.add(user)
    await session.flush()
    upload = Upload(
        id=upload_id, user_id=user_id, file_name="t.csv",
        s3_key=f"{user_id}/t.csv", file_size=100, mime_type="text/csv",
    )
    session.add(upload)
    await session.flush()
    job = ProcessingJob(
        id=job_id, user_id=user_id, upload_id=upload_id,
        status=status,
        step="ingestion" if status == "processing" else ("done" if status == "completed" else None),
        progress=30 if status == "processing" else (100 if status == "completed" else 0),
        error_code=error_code, error_message=error_message,
    )
    session.add(job)
    await session.commit()
    return user_id, job_id


# ── SSE Endpoint Tests ──────────────────────────────────────────────────


class TestSSEEndpointTenantIsolation:
    """7.2 — SSE endpoint enforces tenant isolation."""

    @pytest.mark.asyncio
    async def test_sse_returns_404_for_other_users_job(
        self, client, async_session, mock_rate_limiter
    ):
        """User A cannot access user B's job SSE stream."""
        # Create user A (authenticated)
        user_a = User(id=uuid.uuid4(), email="a@t.com", cognito_sub="sub-a", locale="en")
        async_session.add(user_a)
        await async_session.flush()

        # Create user B + job
        user_b = User(id=uuid.uuid4(), email="b@t.com", cognito_sub="sub-b", locale="en")
        async_session.add(user_b)
        await async_session.flush()

        upload = Upload(
            id=uuid.uuid4(), user_id=user_b.id, file_name="t.csv",
            s3_key="k", file_size=100, mime_type="text/csv",
        )
        async_session.add(upload)
        await async_session.flush()

        job_id = uuid.uuid4()
        job = ProcessingJob(
            id=job_id, user_id=user_b.id, upload_id=upload.id,
            status="processing", step="ingestion", progress=10,
        )
        async_session.add(job)
        await async_session.commit()

        # Authenticate as user A via query-param token
        with patch("app.api.v1.jobs.verify_token", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = {"sub": "sub-a"}
            response = await client.get(
                f"/api/v1/jobs/{job_id}/stream?token=fake"
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_sse_returns_404_for_nonexistent_job(
        self, client, async_session, mock_rate_limiter
    ):
        """Non-existent job returns 404."""
        user = User(id=uuid.uuid4(), email="x@t.com", cognito_sub="sub-x", locale="en")
        async_session.add(user)
        await async_session.commit()

        with patch("app.api.v1.jobs.verify_token", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = {"sub": "sub-x"}
            response = await client.get(
                f"/api/v1/jobs/{uuid.uuid4()}/stream?token=fake"
            )

        assert response.status_code == 404


class TestSSEEndpointTerminalStates:
    """7.3/7.4 — Terminal events and reconnection support."""

    @pytest.mark.asyncio
    async def test_completed_job_sends_job_complete_event(
        self, client, async_session, mock_rate_limiter
    ):
        """Already-completed job sends job-complete event immediately."""
        user_id, job_id = await _create_user_job_async(async_session, status="completed")

        with patch("app.api.v1.jobs.verify_token", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = {"sub": "sse-sub"}
            with patch("app.api.v1.jobs.get_job_state", new_callable=AsyncMock) as mock_state:
                mock_state.return_value = None
                response = await client.get(
                    f"/api/v1/jobs/{job_id}/stream?token=fake"
                )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        assert "event: job-complete" in response.text
        assert '"status": "completed"' in response.text

    @pytest.mark.asyncio
    async def test_failed_job_sends_job_failed_event(
        self, client, async_session, mock_rate_limiter
    ):
        """Already-failed job sends job-failed event immediately."""
        user_id, job_id = await _create_user_job_async(
            async_session, status="failed",
            error_code="UNSUPPORTED_FORMAT", error_message="Not supported"
        )

        with patch("app.api.v1.jobs.verify_token", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = {"sub": "sse-sub"}
            with patch("app.api.v1.jobs.get_job_state", new_callable=AsyncMock) as mock_state:
                mock_state.return_value = None
                response = await client.get(
                    f"/api/v1/jobs/{job_id}/stream?token=fake"
                )

        assert response.status_code == 200
        assert "event: job-failed" in response.text
        assert "UNSUPPORTED_FORMAT" in response.text

    @pytest.mark.asyncio
    async def test_reconnection_returns_cached_state(
        self, client, async_session, mock_rate_limiter
    ):
        """Reconnecting client receives current state from Redis cache (AC #5)."""
        user_id, job_id = await _create_user_job_async(async_session, status="processing")

        cached_state = {
            "event": "pipeline-progress",
            "jobId": str(job_id),
            "step": "ingestion",
            "progress": 30,
            "message": "Parsing complete",
        }

        async def mock_subscribe(jid):
            yield {"event": "job-complete", "jobId": jid, "status": "completed", "totalInsights": 0}

        with patch("app.api.v1.jobs.verify_token", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = {"sub": "sse-sub"}
            with patch("app.api.v1.jobs.get_job_state", new_callable=AsyncMock) as mock_state:
                mock_state.return_value = cached_state
                with patch("app.api.v1.jobs.subscribe_job_progress", side_effect=mock_subscribe):
                    response = await client.get(
                        f"/api/v1/jobs/{job_id}/stream?token=fake"
                    )

        body = response.text
        assert "event: pipeline-progress" in body
        assert '"progress": 30' in body
        assert "event: job-complete" in body


class TestSSEEndpointStreaming:
    """7.1 — SSE streams progress events correctly."""

    @pytest.mark.asyncio
    async def test_streams_progress_then_complete(
        self, client, async_session, mock_rate_limiter
    ):
        """SSE streams progress events followed by job-complete."""
        user_id, job_id = await _create_user_job_async(async_session, status="processing")
        job_id_str = str(job_id)

        events = [
            {"event": "pipeline-progress", "jobId": job_id_str, "step": "ingestion", "progress": 10, "message": "Reading..."},
            {"event": "pipeline-progress", "jobId": job_id_str, "step": "ingestion", "progress": 30, "message": "Parsing..."},
            {"event": "job-complete", "jobId": job_id_str, "status": "completed", "totalInsights": 0},
        ]

        async def mock_subscribe(jid):
            for event in events:
                yield event

        with patch("app.api.v1.jobs.verify_token", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = {"sub": "sse-sub"}
            with patch("app.api.v1.jobs.get_job_state", new_callable=AsyncMock) as mock_state:
                mock_state.return_value = None
                with patch("app.api.v1.jobs.subscribe_job_progress", side_effect=mock_subscribe):
                    response = await client.get(
                        f"/api/v1/jobs/{job_id}/stream?token=fake"
                    )

        body = response.text
        assert body.count("event: pipeline-progress") == 2
        assert body.count("event: job-complete") == 1
        assert '"progress": 10' in body
        assert '"progress": 30' in body


# ── Redis Pub/Sub Utilities Tests ────────────────────────────────────────


class TestRedisPubSubUtilities:
    """7.5 — Redis pub/sub publish and subscribe utilities."""

    def test_publish_job_progress_calls_redis(self):
        """publish_job_progress publishes to correct channel and stores state."""
        with patch("app.core.redis.sync_redis.from_url") as mock_from_url:
            mock_client = mock_from_url.return_value
            from app.core.redis import publish_job_progress

            data = {"event": "pipeline-progress", "jobId": "test-123", "progress": 50}
            publish_job_progress("test-123", data)

            # Verify SET for state storage
            mock_client.set.assert_called_once()
            set_args = mock_client.set.call_args
            assert "job:state:test-123" in set_args[0]
            assert set_args[1]["ex"] == 3600

            # Verify PUBLISH
            mock_client.publish.assert_called_once()
            pub_args = mock_client.publish.call_args[0]
            assert pub_args[0] == "job:progress:test-123"
            assert json.loads(pub_args[1]) == data

            mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_state_returns_cached_state(self):
        """get_job_state returns parsed JSON from Redis."""
        state_data = {"event": "pipeline-progress", "progress": 30}

        with patch("app.core.redis.get_redis", new_callable=AsyncMock) as mock_get:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = json.dumps(state_data)
            mock_get.return_value = mock_redis

            from app.core.redis import get_job_state
            result = await get_job_state("test-123")

        assert result == state_data
        mock_redis.get.assert_called_once_with("job:state:test-123")

    @pytest.mark.asyncio
    async def test_get_job_state_returns_none_when_missing(self):
        """get_job_state returns None when no state cached."""
        with patch("app.core.redis.get_redis", new_callable=AsyncMock) as mock_get:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = None
            mock_get.return_value = mock_redis

            from app.core.redis import get_job_state
            result = await get_job_state("test-123")

        assert result is None


# ── Celery Task Redis Publishing Tests ───────────────────────────────────


class TestCeleryTaskPublishesProgress:
    """7.6 — Celery task publishes progress events to Redis."""

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_happy_path_publishes_progress_events(
        self, mock_get_session, mock_boto_client, mock_publish, sync_engine
    ):
        """Celery task publishes progress at each checkpoint and job-complete on success."""
        import io

        user_id, job_id = _seed(sync_engine, status="validated")

        @contextmanager
        def _cm():
            s = Session(sync_engine)
            try:
                yield s
            finally:
                s.close()

        mock_get_session.side_effect = _cm

        csv_data = (
            "Дата і час операції;Опис операції;MCC;Сума в валюті картки (UAH);Залишок на рахунку (UAH)\n"
            "01.01.2024 12:00:00;Store;5411;-100.50;5000.00\n"
        ).encode("utf-8")

        mock_s3 = mock_boto_client.return_value
        mock_s3.get_object.return_value = {"Body": io.BytesIO(csv_data)}

        from app.tasks.processing_tasks import process_upload
        result = process_upload(str(job_id))

        assert result["parsed_count"] == 1

        calls = mock_publish.call_args_list
        # Events: 10% ingestion, 30% parsing, 40% categorization start,
        # 60% categorization done, 80% education done, 90% profile build,
        # 92% health-score, N x insight-ready, job-complete
        progress_calls = [c for c in calls if c[0][1]["event"] == "pipeline-progress"]
        insight_calls = [c for c in calls if c[0][1]["event"] == "insight-ready"]
        complete_calls = [c for c in calls if c[0][1]["event"] == "job-complete"]

        assert len(progress_calls) == 7
        assert len(complete_calls) == 1

        assert progress_calls[0][0][1]["progress"] == 10
        assert progress_calls[1][0][1]["progress"] == 30

        assert progress_calls[2][0][1]["step"] == "categorization"
        assert progress_calls[2][0][1]["progress"] == 40

        assert progress_calls[3][0][1]["step"] == "categorization"
        assert progress_calls[3][0][1]["progress"] == 60

        assert progress_calls[4][0][1]["step"] == "education"
        assert progress_calls[4][0][1]["progress"] == 80

        assert progress_calls[5][0][1]["step"] == "profile"
        assert progress_calls[5][0][1]["progress"] == 90

        assert progress_calls[6][0][1]["step"] == "health-score"
        assert progress_calls[6][0][1]["progress"] == 92
        assert progress_calls[5][0][1]["progress"] == 90

        # Each insight card produces an insight-ready event
        for ic in insight_calls:
            assert ic[0][1]["event"] == "insight-ready"
            assert "insightId" in ic[0][1]

        assert complete_calls[0][0][1]["status"] == "completed"
        assert complete_calls[0][0][1]["totalInsights"] == len(insight_calls)

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_failure_publishes_job_failed_event(
        self, mock_get_session, mock_boto_client, mock_publish, sync_engine
    ):
        """Celery task publishes job-failed event on error."""
        import io

        user_id = uuid.uuid4()
        upload_id = uuid.uuid4()
        job_id = uuid.uuid4()

        with Session(sync_engine) as s:
            s.add(User(id=user_id, email="fail@t.com", cognito_sub="f-sub", locale="en"))
            s.flush()
            s.add(Upload(
                id=upload_id, user_id=user_id, file_name="t.csv",
                s3_key="k", file_size=100, mime_type="text/csv",
                detected_format="totally_unknown", detected_encoding="utf-8",
                detected_delimiter=";",
            ))
            s.flush()
            s.add(ProcessingJob(id=job_id, user_id=user_id, upload_id=upload_id, status="validated"))
            s.commit()

        @contextmanager
        def _cm():
            s = Session(sync_engine)
            try:
                yield s
            finally:
                s.close()

        mock_get_session.side_effect = _cm

        mock_s3 = mock_boto_client.return_value
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"invalid,data\n1,2")}

        from app.tasks.processing_tasks import process_upload
        result = process_upload(str(job_id))

        assert result["error"] == "unsupported_format"

        failed_calls = [
            c for c in mock_publish.call_args_list
            if c[0][1].get("event") == "job-failed"
        ]
        assert len(failed_calls) == 1
        assert failed_calls[0][0][1]["error"]["code"] == "UNSUPPORTED_FORMAT"


def _seed(engine, status="processing", error_code=None, error_message=None):
    """Create user + upload + job. Returns (user_id, job_id)."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    job_id = uuid.uuid4()
    with Session(engine) as s:
        s.add(User(id=user_id, email="sse@test.com", cognito_sub="sse-sub", locale="en"))
        s.flush()
        s.add(Upload(
            id=upload_id, user_id=user_id, file_name="t.csv",
            s3_key=f"{user_id}/t.csv", file_size=100, mime_type="text/csv",
        ))
        s.flush()
        s.add(ProcessingJob(
            id=job_id, user_id=user_id, upload_id=upload_id,
            status=status,
            step="ingestion" if status == "processing" else ("done" if status == "completed" else None),
            progress=30 if status == "processing" else (100 if status == "completed" else 0),
            error_code=error_code, error_message=error_message,
        ))
        s.commit()
    return user_id, job_id


# ── SSE Auth Edge Case Tests ──────────────────────────────────────────


class TestSSEAuthEdgeCases:
    """M4 — Auth edge cases for SSE query-param token."""

    @pytest.mark.asyncio
    async def test_sse_returns_401_for_missing_sub_claim(
        self, client, async_session, mock_rate_limiter
    ):
        """Token without sub claim returns 401."""
        user_id, job_id = await _create_user_job_async(async_session, status="processing")

        with patch("app.api.v1.jobs.verify_token", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = {"aud": "some-audience"}  # no "sub"
            response = await client.get(
                f"/api/v1/jobs/{job_id}/stream?token=fake"
            )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_sse_returns_401_for_unknown_user(
        self, client, async_session, mock_rate_limiter
    ):
        """Valid token but user not in database returns 401."""
        user_id, job_id = await _create_user_job_async(async_session, status="processing")

        with patch("app.api.v1.jobs.verify_token", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = {"sub": "non-existent-cognito-sub"}
            response = await client.get(
                f"/api/v1/jobs/{job_id}/stream?token=fake"
            )

        assert response.status_code == 401


# ── SSE Heartbeat Test ────────────────────────────────────────────────


class TestSSEHeartbeat:
    """M3 — SSE heartbeat/keepalive behavior."""

    @pytest.mark.asyncio
    async def test_heartbeat_sent_when_no_events(
        self, client, async_session, mock_rate_limiter
    ):
        """SSE stream sends heartbeat comment when no events arrive within interval."""
        import asyncio as _asyncio

        user_id, job_id = await _create_user_job_async(async_session, status="processing")

        async def mock_subscribe(jid):
            # Sleep longer than heartbeat interval so wait_for times out,
            # triggering a heartbeat. The CancelledError from wait_for
            # terminates the generator, ending the stream.
            await _asyncio.sleep(10)
            yield {"event": "job-complete", "jobId": jid, "status": "completed", "totalInsights": 0}

        with patch("app.api.v1.jobs.verify_token", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = {"sub": "sse-sub"}
            with patch("app.api.v1.jobs.get_job_state", new_callable=AsyncMock) as mock_state:
                mock_state.return_value = None
                with patch("app.api.v1.jobs.SSE_HEARTBEAT_INTERVAL", 0.01):
                    with patch("app.api.v1.jobs.subscribe_job_progress", side_effect=mock_subscribe):
                        response = await client.get(
                            f"/api/v1/jobs/{job_id}/stream?token=fake"
                        )

        body = response.text
        assert ": heartbeat" in body
