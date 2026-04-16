"""Tests for Celery processing task (Story 2.5)."""
import io
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock, call, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from app.models.processing_job import ProcessingJob
from app.models.upload import Upload
from app.models.transaction import Transaction
from app.models.user import User


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def _mock_sync_session_cm(engine):
    """Create a context manager mock compatible with get_sync_session()."""
    @contextmanager
    def _cm():
        session = Session(engine)
        try:
            yield session
        finally:
            session.close()
    return _cm


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


def _seed_data(engine):
    """Create user, upload, and job records. Returns (user, upload, job) with their IDs."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    job_id = uuid.uuid4()

    with Session(engine) as session:
        user = User(id=user_id, email="celery@test.com", cognito_sub="celery-test-sub", locale="en")
        session.add(user)
        session.flush()

        upload = Upload(
            id=upload_id, user_id=user_id, file_name="test.csv",
            s3_key=f"{user_id}/test_original.csv", file_size=1024,
            mime_type="text/csv", detected_format="monobank", detected_encoding="utf-8",
            detected_delimiter=";",
        )
        session.add(upload)
        session.flush()

        job = ProcessingJob(id=job_id, user_id=user_id, upload_id=upload_id, status="validated")
        session.add(job)
        session.commit()

    return user_id, upload_id, job_id


def _get_job(engine, job_id):
    """Load a fresh ProcessingJob from the DB."""
    with Session(engine) as session:
        job = session.get(ProcessingJob, job_id)
        # Expunge so we can use it outside the session
        if job:
            session.expunge(job)
        return job


MONOBANK_CSV = (
    "Дата і час операції;Опис операції;MCC;Сума в валюті картки (UAH);Залишок на рахунку (UAH)\n"
    "01.01.2024 12:00:00;Grocery Store;5411;-100.50;5000.00\n"
    "02.01.2024 14:30:00;Coffee Shop;5814;-45.00;4955.00\n"
).encode("utf-8")


class TestProcessUploadHappyPath:
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_happy_path_completes_job(self, mock_get_session, mock_boto_client, sync_engine):
        """Happy path: task runs, transactions persisted, job status = 'completed'."""
        user_id, upload_id, job_id = _seed_data(sync_engine)

        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        from app.tasks.processing_tasks import process_upload

        result = process_upload(str(job_id))

        assert result["parsed_count"] == 2
        assert result["total_rows"] == 2

        job = _get_job(sync_engine, job_id)
        assert job.status == "completed"
        assert job.step == "done"
        assert job.progress == 100
        assert job.result_data is not None
        assert job.result_data["parsed_count"] == 2

        with Session(sync_engine) as s:
            txns = s.exec(select(Transaction)).all()
            assert len(txns) == 2


class TestProcessUploadRetry:
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_transient_s3_error_triggers_retry(self, mock_get_session, mock_boto_client, sync_engine):
        """Transient S3 error triggers retry with exponential backoff."""
        from botocore.exceptions import ClientError
        from celery.exceptions import Retry

        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "S3 temporarily unavailable"}},
            "GetObject",
        )
        mock_boto_client.return_value = mock_s3

        from app.tasks.processing_tasks import process_upload

        # Patch retry to raise Retry (as real Celery does)
        with patch.object(process_upload, "retry", side_effect=Retry()) as mock_retry:
            with pytest.raises(Retry):
                process_upload(str(job_id))

            mock_retry.assert_called_once()
            # Verify exponential backoff countdown is passed
            call_kwargs = mock_retry.call_args[1]
            assert "countdown" in call_kwargs

    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_permanent_error_no_retry(self, mock_get_session, mock_boto_client, sync_engine):
        """UnsupportedFormatError does NOT trigger retry, job marked failed."""
        user_id, upload_id, job_id = _seed_data(sync_engine)

        # Change detected_format to something unsupported
        with Session(sync_engine) as s:
            upload = s.get(Upload, upload_id)
            upload.detected_format = "totally_unknown"
            s.add(upload)
            s.commit()

        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"invalid,data\n1,2")}
        mock_boto_client.return_value = mock_s3

        from app.tasks.processing_tasks import process_upload

        result = process_upload(str(job_id))

        assert result["error"] == "unsupported_format"

        job = _get_job(sync_engine, job_id)
        assert job.status == "failed"
        assert job.error_code == "UNSUPPORTED_FORMAT"

    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_max_retries_exceeded(self, mock_get_session, mock_boto_client, sync_engine):
        """Max retries exceeded marks job as failed with MAX_RETRIES_EXCEEDED."""
        from botocore.exceptions import ClientError
        from celery.exceptions import MaxRetriesExceededError

        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "S3 down"}},
            "GetObject",
        )
        mock_boto_client.return_value = mock_s3

        from app.tasks.processing_tasks import process_upload

        # retry raises MaxRetriesExceededError — task catches it and marks failed
        with patch.object(process_upload, "retry", side_effect=MaxRetriesExceededError()):
            result = process_upload(str(job_id))

        assert result["error"] == "max_retries_exceeded"

        job = _get_job(sync_engine, job_id)
        assert job.status == "failed"
        assert job.error_code == "MAX_RETRIES_EXCEEDED"


class TestProcessUploadPartialResults:
    @patch("app.tasks.processing_tasks.sync_parse_and_store_transactions")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_partial_results_preserved_on_failure(self, mock_get_session, mock_boto_client, mock_parse, sync_engine):
        """Failure after partial parse preserves partial transactions in DB."""
        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        def partial_parse(session, user_id, upload_id, file_bytes, format_result):
            txn = Transaction(
                user_id=user_id, upload_id=upload_id, date=_utcnow(),
                description="Partial txn", amount=-100, currency_code="UAH",
                dedup_hash="fakehash_partial_test",
            )
            session.add(txn)
            session.flush()
            raise ValueError("Parse error after partial results")

        mock_parse.side_effect = partial_parse

        from app.tasks.processing_tasks import process_upload

        result = process_upload(str(job_id))

        assert result["error"] == "data_error"

        job = _get_job(sync_engine, job_id)
        assert job.status == "failed"
        assert job.error_code == "DATA_ERROR"

        # Verify partial transaction was preserved (not rolled back)
        with Session(sync_engine) as s:
            txns = s.exec(select(Transaction)).all()
            assert len(txns) == 1
            assert txns[0].description == "Partial txn"


class TestInsightReadySSEEvents:
    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.build_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_insight_ready_events_emitted_per_insight(
        self, mock_get_session, mock_boto_client, mock_build_pipeline, mock_publish, sync_engine
    ):
        """After batch commit, one insight-ready event is emitted per persisted insight."""
        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        insight_cards = [
            {
                "headline": "Food spending up",
                "key_metric": "₴1000",
                "why_it_matters": "Matters",
                "deep_dive": "Details",
                "severity": "high",
                "category": "food",
            },
            {
                "headline": "Transport costs",
                "key_metric": "₴500",
                "why_it_matters": "Matters",
                "deep_dive": "Details",
                "severity": "medium",
                "category": "transport",
            },
        ]

        mock_build_pipeline.return_value.invoke.return_value = {
            "categorized_transactions": [],
            "insight_cards": insight_cards,
            "total_tokens_used": 0,
            "errors": [],
        }

        from app.tasks.processing_tasks import process_upload

        process_upload(str(job_id))

        # Collect all insight-ready calls
        insight_ready_calls = [
            c for c in mock_publish.call_args_list
            if c.args[1].get("event") == "insight-ready"
        ]

        assert len(insight_ready_calls) == 2

        categories = {c.args[1]["type"] for c in insight_ready_calls}
        assert categories == {"food", "transport"}

        for c in insight_ready_calls:
            payload = c.args[1]
            assert payload["jobId"] == str(job_id)
            assert "insightId" in payload
            assert payload["insightId"] != ""

        # Verify event ordering: education pipeline-progress must come BEFORE insight-ready
        all_events = [c.args[1]["event"] for c in mock_publish.call_args_list]
        education_idx = next(
            i for i, c in enumerate(mock_publish.call_args_list)
            if c.args[1].get("event") == "pipeline-progress" and c.args[1].get("step") == "education"
        )
        first_insight_idx = next(
            i for i, c in enumerate(mock_publish.call_args_list)
            if c.args[1].get("event") == "insight-ready"
        )
        assert education_idx < first_insight_idx, (
            f"Education progress event (index {education_idx}) must come before "
            f"first insight-ready event (index {first_insight_idx})"
        )

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.build_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_no_insight_ready_events_when_no_insights(
        self, mock_get_session, mock_boto_client, mock_build_pipeline, mock_publish, sync_engine
    ):
        """No insight-ready events emitted when pipeline produces no insight cards."""
        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        mock_build_pipeline.return_value.invoke.return_value = {
            "categorized_transactions": [],
            "insight_cards": [],
            "total_tokens_used": 0,
            "errors": [],
        }

        from app.tasks.processing_tasks import process_upload

        process_upload(str(job_id))

        insight_ready_calls = [
            c for c in mock_publish.call_args_list
            if c.args[1].get("event") == "insight-ready"
        ]

        assert len(insight_ready_calls) == 0


class TestLiteracyLevelDetection:
    """Tests for literacy level detection in process_upload (Story 3.8)."""

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.build_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_first_upload_sets_beginner(
        self, mock_get_session, mock_boto_client, mock_build_pipeline, mock_publish, sync_engine
    ):
        """First upload for a user sets literacy_level to 'beginner'."""
        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        mock_build_pipeline.return_value.invoke.return_value = {
            "categorized_transactions": [],
            "insight_cards": [],
            "total_tokens_used": 0,
            "errors": [],
        }

        from app.tasks.processing_tasks import process_upload
        process_upload(str(job_id))

        # Verify pipeline was invoked with literacy_level="beginner"
        call_args = mock_build_pipeline.return_value.invoke.call_args[0][0]
        assert call_args["literacy_level"] == "beginner"

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.build_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_three_uploads_within_7_days_stays_beginner(
        self, mock_get_session, mock_boto_client, mock_build_pipeline, mock_publish, sync_engine
    ):
        """3+ uploads but first upload < 7 days ago → beginner."""
        user_id, upload_id, job_id = _seed_data(sync_engine)

        # Add 2 more uploads (total 3), all recent
        with Session(sync_engine) as s:
            for i in range(2):
                extra_upload = Upload(
                    user_id=user_id, file_name=f"extra{i}.csv",
                    s3_key=f"{user_id}/extra{i}.csv", file_size=100,
                    mime_type="text/csv", detected_format="monobank",
                    detected_encoding="utf-8", detected_delimiter=";",
                )
                s.add(extra_upload)
            s.commit()

        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        mock_build_pipeline.return_value.invoke.return_value = {
            "categorized_transactions": [],
            "insight_cards": [],
            "total_tokens_used": 0,
            "errors": [],
        }

        from app.tasks.processing_tasks import process_upload
        process_upload(str(job_id))

        call_args = mock_build_pipeline.return_value.invoke.call_args[0][0]
        assert call_args["literacy_level"] == "beginner"

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.build_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_three_uploads_after_7_days_sets_intermediate(
        self, mock_get_session, mock_boto_client, mock_build_pipeline, mock_publish, sync_engine
    ):
        """3+ uploads AND first upload >= 7 days ago → intermediate."""
        from datetime import timedelta

        user_id, upload_id, job_id = _seed_data(sync_engine)

        # Backdate the first upload to 10 days ago and add more uploads
        with Session(sync_engine) as s:
            upload = s.get(Upload, upload_id)
            upload.created_at = _utcnow() - timedelta(days=10)
            s.add(upload)

            for i in range(2):
                extra_upload = Upload(
                    user_id=user_id, file_name=f"extra{i}.csv",
                    s3_key=f"{user_id}/extra{i}.csv", file_size=100,
                    mime_type="text/csv", detected_format="monobank",
                    detected_encoding="utf-8", detected_delimiter=";",
                )
                s.add(extra_upload)
            s.commit()

        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        mock_build_pipeline.return_value.invoke.return_value = {
            "categorized_transactions": [],
            "insight_cards": [],
            "total_tokens_used": 0,
            "errors": [],
        }

        from app.tasks.processing_tasks import process_upload
        process_upload(str(job_id))

        call_args = mock_build_pipeline.return_value.invoke.call_args[0][0]
        assert call_args["literacy_level"] == "intermediate"


    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.build_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_three_uploads_exactly_7_days_sets_intermediate(
        self, mock_get_session, mock_boto_client, mock_build_pipeline, mock_publish, sync_engine
    ):
        """3+ uploads AND first upload exactly 7 days ago → intermediate (boundary test)."""
        from datetime import timedelta

        user_id, upload_id, job_id = _seed_data(sync_engine)

        with Session(sync_engine) as s:
            upload = s.get(Upload, upload_id)
            upload.created_at = _utcnow() - timedelta(days=7)
            s.add(upload)

            for i in range(2):
                extra_upload = Upload(
                    user_id=user_id, file_name=f"boundary{i}.csv",
                    s3_key=f"{user_id}/boundary{i}.csv", file_size=100,
                    mime_type="text/csv", detected_format="monobank",
                    detected_encoding="utf-8", detected_delimiter=";",
                )
                s.add(extra_upload)
            s.commit()

        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        mock_build_pipeline.return_value.invoke.return_value = {
            "categorized_transactions": [],
            "insight_cards": [],
            "total_tokens_used": 0,
            "errors": [],
        }

        from app.tasks.processing_tasks import process_upload
        process_upload(str(job_id))

        call_args = mock_build_pipeline.return_value.invoke.call_args[0][0]
        assert call_args["literacy_level"] == "intermediate"


class TestCircuitBreakerHandling:
    """Tests for SERVICE_UNAVAILABLE error when circuit breaker is open (Story 6.2, AC #4)."""

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.build_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_circuit_breaker_open_marks_service_unavailable(
        self, mock_get_session, mock_boto_client, mock_build_pipeline, mock_publish, sync_engine
    ):
        """CircuitBreakerOpenError sets job to failed with SERVICE_UNAVAILABLE code."""
        from app.agents.circuit_breaker import CircuitBreakerOpenError

        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        mock_build_pipeline.return_value.invoke.side_effect = CircuitBreakerOpenError("anthropic")

        from app.tasks.processing_tasks import process_upload

        result = process_upload(str(job_id))

        assert result["error"] == "service_unavailable"

        job = _get_job(sync_engine, job_id)
        assert job.status == "failed"
        assert job.error_code == "SERVICE_UNAVAILABLE"
        assert job.is_retryable is True

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.build_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_circuit_breaker_publishes_job_failed_event(
        self, mock_get_session, mock_boto_client, mock_build_pipeline, mock_publish, sync_engine
    ):
        """CircuitBreakerOpenError publishes job-failed SSE event with SERVICE_UNAVAILABLE code."""
        from app.agents.circuit_breaker import CircuitBreakerOpenError

        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        mock_build_pipeline.return_value.invoke.side_effect = CircuitBreakerOpenError("anthropic")

        from app.tasks.processing_tasks import process_upload

        process_upload(str(job_id))

        failed_calls = [
            c for c in mock_publish.call_args_list
            if c.args[1].get("event") == "job-failed"
        ]
        assert len(failed_calls) >= 1
        payload = failed_calls[-1].args[1]
        assert payload["error"]["code"] == "SERVICE_UNAVAILABLE"


class TestPipelineMetrics:
    """Tests for pipeline performance metrics tracking (Story 6.5)."""

    @patch("app.tasks.processing_tasks.logger")
    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.build_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_successful_pipeline_records_timing_metrics(
        self, mock_get_session, mock_boto_client, mock_build_pipeline, mock_publish, mock_logger, sync_engine
    ):
        """Successful pipeline sets started_at, agent_timings in result_data, and emits pipeline_completed log."""
        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        mock_build_pipeline.return_value.invoke.return_value = {
            "categorized_transactions": [],
            "insight_cards": [],
            "total_tokens_used": 0,
            "errors": [],
        }

        from app.tasks.processing_tasks import process_upload

        result = process_upload(str(job_id))

        # Verify started_at is set
        job = _get_job(sync_engine, job_id)
        assert job.started_at is not None

        # Verify agent_timings in result_data
        assert "agent_timings" in job.result_data
        timings = job.result_data["agent_timings"]
        assert isinstance(timings["ingestion_ms"], int)
        assert timings["ingestion_ms"] >= 0
        assert isinstance(timings["categorization_ms"], int)
        assert timings["categorization_ms"] >= 0
        assert isinstance(timings["education_ms"], int)
        assert timings["education_ms"] >= 0

        # Verify total_ms in result_data
        assert isinstance(job.result_data["total_ms"], int)
        assert job.result_data["total_ms"] >= 0

        # Verify pipeline_completed log entry
        pipeline_calls = [
            c for c in mock_logger.info.call_args_list
            if c.args[0] == "pipeline_completed"
        ]
        assert len(pipeline_calls) == 1
        extra = pipeline_calls[0].kwargs["extra"]
        assert extra["job_id"] == str(job_id)
        assert extra["upload_id"] == str(upload_id)
        assert extra["file_size"] == 1024
        assert extra["file_type"] == "text/csv"
        assert extra["bank_format_detected"] == "monobank"
        assert extra["status"] == "completed"

    @patch("app.tasks.processing_tasks.logger")
    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.build_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_failed_pipeline_emits_metrics_log(
        self, mock_get_session, mock_boto_client, mock_build_pipeline, mock_publish, mock_logger, sync_engine
    ):
        """Failed pipeline emits pipeline_metrics log with status=failed and error_type."""
        from app.agents.circuit_breaker import CircuitBreakerOpenError

        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        mock_build_pipeline.return_value.invoke.side_effect = CircuitBreakerOpenError("anthropic")

        from app.tasks.processing_tasks import process_upload

        result = process_upload(str(job_id))

        assert result["error"] == "service_unavailable"

        # Verify pipeline_metrics log entry for failure
        metrics_calls = [
            c for c in mock_logger.info.call_args_list
            if c.args[0] == "pipeline_metrics"
        ]
        assert len(metrics_calls) == 1
        extra = metrics_calls[0].kwargs["extra"]
        assert extra["job_id"] == str(job_id)
        assert extra["upload_id"] == str(upload_id)
        assert extra["user_id"] == str(user_id)
        assert extra["file_size"] == 1024
        assert extra["file_type"] == "text/csv"
        assert extra["bank_format_detected"] == "monobank"
        assert extra["status"] == "failed"
        assert extra["error_type"] == "SERVICE_UNAVAILABLE"


class TestProcessingJobModel:
    """Model-level tests for ProcessingJob (Story 6.5)."""

    def test_started_at_defaults_to_none(self):
        """ProcessingJob can be constructed with started_at=None (default)."""
        job = ProcessingJob(
            user_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
        )
        assert job.started_at is None

    def test_started_at_accepts_datetime(self):
        """ProcessingJob can be constructed with a datetime value for started_at."""
        now = _utcnow()
        job = ProcessingJob(
            user_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            started_at=now,
        )
        assert job.started_at == now


class TestResumeUploadMetrics:
    """Tests for resume_upload timing/metrics (Story 6.5, Task 3)."""

    @patch("app.tasks.processing_tasks.logger")
    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.resume_pipeline")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_resume_records_timing_and_emits_log(
        self, mock_get_session, mock_resume_pipeline, mock_publish, mock_logger, sync_engine
    ):
        """resume_upload sets started_at, stores agent_timings, and emits pipeline_completed log."""
        user_id, upload_id, job_id = _seed_data(sync_engine)

        # Mark job as failed so it's eligible for resume
        with Session(sync_engine) as s:
            job = s.get(ProcessingJob, job_id)
            job.status = "failed"
            job.failed_step = "categorization"
            s.add(job)
            s.commit()

        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_resume_pipeline.return_value = {
            "upload_id": str(upload_id),
            "categorized_transactions": [],
            "insight_cards": [],
            "total_tokens_used": 0,
            "errors": [],
        }

        from app.tasks.processing_tasks import resume_upload

        result = resume_upload(str(job_id))

        assert result["status"] == "completed"

        # Verify started_at is set
        job = _get_job(sync_engine, job_id)
        assert job.started_at is not None

        # Verify agent_timings in result_data
        assert "agent_timings" in job.result_data
        timings = job.result_data["agent_timings"]
        assert isinstance(timings["categorization_ms"], int)
        assert timings["categorization_ms"] >= 0
        assert isinstance(timings["education_ms"], int)
        assert timings["education_ms"] >= 0

        # Verify total_ms
        assert isinstance(job.result_data["total_ms"], int)
        assert job.result_data["total_ms"] >= 0

        # Verify pipeline_completed log with status="resumed_completed"
        pipeline_calls = [
            c for c in mock_logger.info.call_args_list
            if c.args[0] == "pipeline_completed"
        ]
        assert len(pipeline_calls) == 1
        extra = pipeline_calls[0].kwargs["extra"]
        assert extra["job_id"] == str(job_id)
        assert extra["upload_id"] == str(upload_id)
        assert extra["status"] == "resumed_completed"
        assert extra["categorization_ms"] >= 0
        assert extra["education_ms"] >= 0
        assert extra["total_ms"] >= 0


class TestProcessUploadPerformance:
    @pytest.mark.slow
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_500_transactions_under_60_seconds(self, mock_get_session, mock_boto_client, sync_engine):
        """500 transactions processed within 60 seconds."""
        import time

        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        header = "Дата і час операції;Опис операції;MCC;Сума в валюті картки (UAH);Залишок на рахунку (UAH)\n"
        rows = []
        for i in range(500):
            day = (i % 28) + 1
            rows.append(f"{day:02d}.01.2024 12:00:00;Store {i};5411;-{i+1}.00;{10000-i}.00")
        csv_content = (header + "\n".join(rows)).encode("utf-8")

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(csv_content)}
        mock_boto_client.return_value = mock_s3

        from app.tasks.processing_tasks import process_upload

        start = time.time()
        result = process_upload(str(job_id))
        elapsed = time.time() - start

        assert result["parsed_count"] == 500
        assert elapsed < 60, f"Processing took {elapsed:.1f}s, exceeds 60s limit"

        job = _get_job(sync_engine, job_id)
        assert job.status == "completed"


# ──────── Story 2.8: Upload Completion UX & Summary ────────


class TestProcessUploadSummaryPayload:
    """Story 2.8 — job-complete payload and result_data include bank/summary fields."""

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_result_data_contains_summary_fields(
        self, mock_get_session, mock_boto_client, mock_publish, sync_engine
    ):
        """After successful processing, job.result_data carries summary fields for fallback."""
        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        from app.tasks.processing_tasks import process_upload
        process_upload(str(job_id))

        job = _get_job(sync_engine, job_id)
        assert job.status == "completed"
        assert job.result_data is not None
        assert job.result_data["bank_name"] == "Monobank"
        assert job.result_data["date_range_start"] == "2024-01-01"
        assert job.result_data["date_range_end"] == "2024-01-02"
        assert "insight_count" in job.result_data
        assert "new_transactions" in job.result_data

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_job_complete_payload_has_bank_name_and_date_range(
        self, mock_get_session, mock_boto_client, mock_publish, sync_engine
    ):
        """Published job-complete SSE payload includes bankName, transactionCount, dateRange, totalInsights."""
        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        from app.tasks.processing_tasks import process_upload
        process_upload(str(job_id))

        complete_calls = [
            c for c in mock_publish.call_args_list
            if c.args[1].get("event") == "job-complete"
        ]
        assert len(complete_calls) == 1
        payload = complete_calls[0].args[1]

        assert payload["bankName"] == "Monobank"
        assert payload["transactionCount"] == 2
        assert payload["dateRange"] == {"start": "2024-01-01", "end": "2024-01-02"}
        assert "totalInsights" in payload

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.sync_parse_and_store_transactions")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_job_complete_payload_has_null_date_range_when_no_transactions(
        self, mock_get_session, mock_boto_client, mock_parse, mock_publish, sync_engine
    ):
        """When no transactions are persisted, dateRange is None and no crash occurs."""
        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        # Simulate parser that persists nothing (e.g., all flagged/duplicates)
        class _EmptyResult:
            total_rows = 0
            parsed_count = 0
            flagged_count = 0
            persisted_count = 0
            duplicates_skipped = 0
        mock_parse.return_value = _EmptyResult()

        from app.tasks.processing_tasks import process_upload
        process_upload(str(job_id))

        complete_calls = [
            c for c in mock_publish.call_args_list
            if c.args[1].get("event") == "job-complete"
        ]
        assert len(complete_calls) == 1
        payload = complete_calls[0].args[1]

        assert payload["dateRange"] is None
        # bankName still populated from detected_format
        assert payload["bankName"] == "Monobank"

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_unknown_bank_format_emits_null_bank_name(
        self, mock_get_session, mock_boto_client, mock_publish, sync_engine
    ):
        """When detected_format is outside BANK_DISPLAY_NAMES, bankName is None (frontend falls back)."""
        user_id, upload_id, job_id = _seed_data(sync_engine)

        # Change upload to a format not in BANK_DISPLAY_NAMES but still parseable as monobank CSV
        with Session(sync_engine) as s:
            upload = s.get(Upload, upload_id)
            upload.detected_format = "some_new_bank"
            s.add(upload)
            s.commit()

        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        from app.tasks.processing_tasks import process_upload
        # format detector will still recognize monobank headers but we test summary uses stored detected_format
        process_upload(str(job_id))

        complete_calls = [
            c for c in mock_publish.call_args_list
            if c.args[1].get("event") == "job-complete"
        ]
        assert len(complete_calls) == 1
        assert complete_calls[0].args[1]["bankName"] is None
