"""Tests for Celery processing task (Story 2.5)."""
import io
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

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
