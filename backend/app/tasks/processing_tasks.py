import logging
import uuid
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.core.database import get_sync_session
from app.core.redis import publish_job_progress
from app.models.processing_job import ProcessingJob
from app.models.upload import Upload
from app.services.format_detector import FormatDetectionResult
from app.services.parser_service import (
    UnsupportedFormatError,
    sync_parse_and_store_transactions,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@celery_app.task(bind=True, max_retries=3, acks_late=True, track_started=True)
def process_upload(self, job_id: str) -> dict:
    """Process an uploaded bank statement file.

    Args:
        job_id: UUID string of the ProcessingJob to process.

    Returns:
        dict with parse results (total_rows, parsed_count, flagged_count).
    """
    with get_sync_session() as session:
        # 1. Load ProcessingJob
        job = session.get(ProcessingJob, uuid.UUID(job_id))
        if job is None:
            logger.error("ProcessingJob not found", extra={"job_id": job_id})
            return {"error": "job_not_found"}

        # 2. Update status to "processing"
        job.status = "processing"
        job.step = "ingestion"
        job.progress = 10
        job.updated_at = _utcnow()
        session.add(job)
        session.commit()

        publish_job_progress(job_id, {
            "event": "pipeline-progress",
            "jobId": job_id,
            "step": "ingestion",
            "progress": 10,
            "message": "Reading transactions...",
        })

        try:
            # 3. Load Upload record for s3_key, format, encoding
            upload = session.get(Upload, job.upload_id)
            if upload is None:
                raise ValueError(f"Upload record not found for upload_id={job.upload_id}")

            # 4. Download file from S3
            s3_client = boto3.client("s3", region_name=settings.S3_REGION)
            s3_response = s3_client.get_object(
                Bucket=settings.S3_UPLOADS_BUCKET,
                Key=upload.s3_key,
            )
            file_bytes = s3_response["Body"].read()

            job.progress = 30
            job.updated_at = _utcnow()
            session.add(job)
            session.commit()

            publish_job_progress(job_id, {
                "event": "pipeline-progress",
                "jobId": job_id,
                "step": "ingestion",
                "progress": 30,
                "message": "Parsing complete",
            })

            # 5. Reconstruct FormatDetectionResult
            format_result = FormatDetectionResult(
                bank_format=upload.detected_format or "unknown",
                encoding=upload.detected_encoding or "utf-8",
                delimiter=upload.detected_delimiter or ";",
                column_count=0,
                confidence_score=1.0,
                header_row=[],
            )

            # 6. Parse and store transactions
            result = sync_parse_and_store_transactions(
                session=session,
                user_id=job.user_id,
                upload_id=upload.id,
                file_bytes=file_bytes,
                format_result=format_result,
            )

            # 7. Update ProcessingJob to "completed"
            job.status = "completed"
            job.step = "done"
            job.progress = 100
            job.result_data = {
                "total_rows": result.total_rows,
                "parsed_count": result.parsed_count,
                "flagged_count": result.flagged_count,
                "persisted_count": result.persisted_count,
            }
            job.updated_at = _utcnow()
            session.add(job)
            session.commit()

            publish_job_progress(job_id, {
                "event": "job-complete",
                "jobId": job_id,
                "status": "completed",
                "totalInsights": 0,
            })

            logger.info(
                "Upload processing completed",
                extra={"job_id": job_id, "result": job.result_data},
            )

            return job.result_data

        except (ClientError, OperationalError) as exc:
            # Transient errors — retry with exponential backoff
            # No partial results to preserve (S3/DB errors happen before or during parsing)
            session.rollback()
            try:
                self.retry(exc=exc, countdown=2 ** self.request.retries)
            except MaxRetriesExceededError:
                _mark_failed(session, job, "MAX_RETRIES_EXCEEDED", str(exc))
                return {"error": "max_retries_exceeded"}

        except UnsupportedFormatError as exc:
            # Permanent error — no partial results (raised before any transactions created)
            session.rollback()
            _mark_failed(session, job, "UNSUPPORTED_FORMAT", str(exc))
            return {"error": "unsupported_format"}

        except (SoftTimeLimitExceeded, ValueError, KeyError, Exception) as exc:
            # Preserve partial results: commit any transactions added to session
            # before marking the job as failed
            _commit_partial_and_mark_failed(session, job, exc, job_id)
            if isinstance(exc, SoftTimeLimitExceeded):
                return {"error": "timeout"}
            if isinstance(exc, (ValueError, KeyError)):
                return {"error": "data_error"}
            return {"error": "unknown_error"}


def _commit_partial_and_mark_failed(
    session, job: ProcessingJob, exc: Exception, job_id: str
) -> None:
    """Commit any partial results (transactions added to session), then mark job as failed.

    If commit fails (e.g. integrity error), rollback and mark failed without partial results.
    """
    if isinstance(exc, SoftTimeLimitExceeded):
        error_code, error_message = "TIMEOUT", "Task exceeded soft time limit"
    elif isinstance(exc, (ValueError, KeyError)):
        error_code, error_message = "DATA_ERROR", str(exc)
    else:
        error_code, error_message = "UNKNOWN_ERROR", str(exc)
        logger.exception("Unexpected error in process_upload", extra={"job_id": job_id})

    try:
        # Try to commit partial transactions before marking failed
        session.commit()
        logger.info("Partial results committed before failure", extra={"job_id": job_id})
    except Exception:
        # Commit failed — rollback and proceed without partial results
        session.rollback()
        logger.warning("Could not commit partial results", extra={"job_id": job_id})

    _mark_failed(session, job, error_code, error_message)


def _mark_failed(session, job: ProcessingJob, error_code: str, error_message: str) -> None:
    """Mark a ProcessingJob as failed with error details."""
    job.status = "failed"
    job.error_code = error_code
    job.error_message = error_message
    job.updated_at = _utcnow()
    session.add(job)
    session.commit()

    publish_job_progress(str(job.id), {
        "event": "job-failed",
        "jobId": str(job.id),
        "status": "failed",
        "error": {"code": error_code, "message": error_message},
    })

    logger.warning(
        "Upload processing failed",
        extra={"job_id": str(job.id), "error_code": error_code, "error_message": error_message},
    )
