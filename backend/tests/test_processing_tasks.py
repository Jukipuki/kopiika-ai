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
    @patch("app.tasks.processing_tasks.financial_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_insight_ready_events_emitted_per_insight(
        self, mock_get_session, mock_boto_client, mock_pipeline, mock_publish, sync_engine
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

        mock_pipeline.invoke.return_value = {
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
    @patch("app.tasks.processing_tasks.financial_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_no_insight_ready_events_when_no_insights(
        self, mock_get_session, mock_boto_client, mock_pipeline, mock_publish, sync_engine
    ):
        """No insight-ready events emitted when pipeline produces no insight cards."""
        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        mock_pipeline.invoke.return_value = {
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
    @patch("app.tasks.processing_tasks.financial_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_first_upload_sets_beginner(
        self, mock_get_session, mock_boto_client, mock_pipeline, mock_publish, sync_engine
    ):
        """First upload for a user sets literacy_level to 'beginner'."""
        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        mock_pipeline.invoke.return_value = {
            "categorized_transactions": [],
            "insight_cards": [],
            "total_tokens_used": 0,
            "errors": [],
        }

        from app.tasks.processing_tasks import process_upload
        process_upload(str(job_id))

        # Verify pipeline was invoked with literacy_level="beginner"
        call_args = mock_pipeline.invoke.call_args[0][0]
        assert call_args["literacy_level"] == "beginner"

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.financial_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_three_uploads_within_7_days_stays_beginner(
        self, mock_get_session, mock_boto_client, mock_pipeline, mock_publish, sync_engine
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

        mock_pipeline.invoke.return_value = {
            "categorized_transactions": [],
            "insight_cards": [],
            "total_tokens_used": 0,
            "errors": [],
        }

        from app.tasks.processing_tasks import process_upload
        process_upload(str(job_id))

        call_args = mock_pipeline.invoke.call_args[0][0]
        assert call_args["literacy_level"] == "beginner"

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.financial_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_three_uploads_after_7_days_sets_intermediate(
        self, mock_get_session, mock_boto_client, mock_pipeline, mock_publish, sync_engine
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

        mock_pipeline.invoke.return_value = {
            "categorized_transactions": [],
            "insight_cards": [],
            "total_tokens_used": 0,
            "errors": [],
        }

        from app.tasks.processing_tasks import process_upload
        process_upload(str(job_id))

        call_args = mock_pipeline.invoke.call_args[0][0]
        assert call_args["literacy_level"] == "intermediate"


    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.financial_pipeline")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_three_uploads_exactly_7_days_sets_intermediate(
        self, mock_get_session, mock_boto_client, mock_pipeline, mock_publish, sync_engine
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

        mock_pipeline.invoke.return_value = {
            "categorized_transactions": [],
            "insight_cards": [],
            "total_tokens_used": 0,
            "errors": [],
        }

        from app.tasks.processing_tasks import process_upload
        process_upload(str(job_id))

        call_args = mock_pipeline.invoke.call_args[0][0]
        assert call_args["literacy_level"] == "intermediate"


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
