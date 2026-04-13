import logging
import uuid
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded
from sqlalchemy.exc import OperationalError
from sqlmodel import func, select

from app.agents.checkpointer import get_checkpointer
from app.agents.circuit_breaker import CircuitBreakerOpenError
from app.agents.pipeline import build_pipeline, resume_pipeline
from app.agents.state import FinancialPipelineState
from app.core.config import settings
from app.core.database import get_sync_session
from app.core.redis import publish_job_progress
from app.models.insight import Insight
from app.models.processing_job import ProcessingJob
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User
from app.services.format_detector import FormatDetectionResult
from app.services.parser_service import (
    UnsupportedFormatError,
    sync_parse_and_store_transactions,
)
from app.services.profile_service import build_or_update_profile
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

            # 7. Run categorization pipeline
            new_transactions = result.persisted_count - result.flagged_count
            categorization_count = 0
            flagged_count_categorization = 0
            total_tokens_used = 0

            publish_job_progress(job_id, {
                "event": "pipeline-progress",
                "jobId": job_id,
                "step": "categorization",
                "progress": 40,
                "message": f"Categorizing {new_transactions} transactions...",
            })

            insight_cards = []
            try:
                # Query stored transactions for this upload
                transactions_for_pipeline = session.exec(
                    select(Transaction).where(Transaction.upload_id == upload.id)
                ).all()

                # Resolve user locale for education agent
                user = session.get(User, job.user_id)
                locale = user.locale if user else "uk"

                # Detect literacy level based on upload history
                upload_stats = session.exec(
                    select(func.count(), func.min(Upload.created_at))
                    .where(Upload.user_id == job.user_id)
                ).one()
                upload_count, first_upload_at = upload_stats
                days_since_first = (_utcnow() - first_upload_at.replace(tzinfo=None)).days if first_upload_at else 0
                literacy_level = "intermediate" if upload_count >= 3 and days_since_first >= 7 else "beginner"

                initial_state: FinancialPipelineState = {
                    "job_id": job_id,
                    "user_id": str(job.user_id),
                    "upload_id": str(upload.id),
                    "transactions": [
                        {
                            "id": str(t.id),
                            "mcc": t.mcc,
                            "description": t.description,
                            "amount": t.amount,
                            "date": str(t.date),
                        }
                        for t in transactions_for_pipeline
                    ],
                    "categorized_transactions": [],
                    "errors": [],
                    "step": "categorization",
                    "total_tokens_used": 0,
                    "locale": locale,
                    "insight_cards": [],
                    "literacy_level": literacy_level,
                    "completed_nodes": [],
                    "failed_node": None,
                }

                with get_checkpointer() as checkpointer:
                    pipeline = build_pipeline(checkpointer=checkpointer)
                    config = {"configurable": {"thread_id": job_id}}
                    result_state = pipeline.invoke(initial_state, config)

                # Bulk-update transactions with categorization results
                cat_lookup = {
                    cat["transaction_id"]: cat
                    for cat in result_state["categorized_transactions"]
                }
                txns = session.exec(
                    select(Transaction).where(Transaction.upload_id == upload.id)
                ).all()
                for txn in txns:
                    cat = cat_lookup.get(str(txn.id))
                    if cat:
                        txn.category = cat["category"]
                        txn.confidence_score = cat["confidence_score"]
                        txn.is_flagged_for_review = cat.get("flagged", False)
                        txn.uncategorized_reason = cat.get("uncategorized_reason")
                        session.add(txn)
                session.commit()

                categorization_count = len(result_state["categorized_transactions"])
                flagged_count_categorization = sum(
                    1 for c in result_state["categorized_transactions"] if c.get("flagged")
                )
                total_tokens_used = result_state.get("total_tokens_used", 0)

                # Persist insight cards from education agent
                insight_cards = result_state.get("insight_cards", [])
                insights: list[Insight] = []
                if insight_cards:
                    for card in insight_cards:
                        insight = Insight(
                            user_id=job.user_id,
                            upload_id=upload.id,
                            headline=card.get("headline", ""),
                            key_metric=card.get("key_metric", ""),
                            why_it_matters=card.get("why_it_matters", ""),
                            deep_dive=card.get("deep_dive", ""),
                            severity=card.get("severity", "medium"),
                            category=card.get("category", "other"),
                        )
                        session.add(insight)
                        insights.append(insight)
                    session.commit()

                publish_job_progress(job_id, {
                    "event": "pipeline-progress",
                    "jobId": job_id,
                    "step": "categorization",
                    "progress": 60,
                    "message": "Categorization complete",
                })

                publish_job_progress(job_id, {
                    "event": "pipeline-progress",
                    "jobId": job_id,
                    "step": "education",
                    "progress": 80,
                    "message": f"Generated {len(insight_cards)} financial insights",
                })

                if insights:
                    for insight in insights:
                        publish_job_progress(job_id, {
                            "event": "insight-ready",
                            "jobId": job_id,
                            "insightId": str(insight.id),
                            "type": insight.category,
                        })

            except Exception as cat_exc:
                logger.warning(
                    "Pipeline agent failed: %s",
                    cat_exc,
                    extra={"job_id": job_id},
                )
                # Track which step failed for retry
                job.failed_step = job.step or "categorization"
                job.last_error_at = _utcnow()
                # Re-raise to let the outer handler manage retry/failure
                raise

            # 8. Build/update financial profile
            publish_job_progress(job_id, {
                "event": "pipeline-progress",
                "jobId": job_id,
                "step": "profile",
                "progress": 90,
                "message": "Building your financial profile...",
            })

            profile_build_ok = False
            try:
                build_or_update_profile(session, job.user_id)
                profile_build_ok = True
            except Exception as profile_exc:
                logger.warning(
                    "Profile build failed (job stays completed): %s",
                    profile_exc,
                    extra={"job_id": job_id},
                )

            # 9. Calculate financial health score (only if profile build succeeded)
            if profile_build_ok:
                publish_job_progress(job_id, {
                    "event": "pipeline-progress",
                    "jobId": job_id,
                    "step": "health-score",
                    "progress": 92,
                    "message": "Calculating your Financial Health Score...",
                })

                try:
                    from app.services.health_score_service import calculate_health_score
                    calculate_health_score(session, job.user_id)
                except Exception as score_exc:
                    logger.warning(
                        "Health score calculation failed (job stays completed): %s",
                        score_exc,
                        extra={"job_id": job_id},
                    )
            else:
                logger.info(
                    "Skipping health score calculation — profile build failed",
                    extra={"job_id": job_id},
                )

            # 10. Update ProcessingJob to "completed"
            job.status = "completed"
            if job.step != "categorization_failed":
                job.step = "done"
            job.progress = 100
            job.result_data = {
                "total_rows": result.total_rows,
                "parsed_count": result.parsed_count,
                "flagged_count": result.flagged_count,
                "persisted_count": result.persisted_count,
                "duplicates_skipped": result.duplicates_skipped,
                "categorization_count": categorization_count,
                "flagged_count_categorization": flagged_count_categorization,
                "total_tokens_used": total_tokens_used,
            }
            job.updated_at = _utcnow()
            session.add(job)
            session.commit()

            publish_job_progress(job_id, {
                "event": "job-complete",
                "jobId": job_id,
                "status": "completed",
                "duplicatesSkipped": result.duplicates_skipped,
                "newTransactions": new_transactions,
                "totalInsights": len(insight_cards),
            })

            logger.info(
                "Upload processing completed",
                extra={"job_id": job_id, "result": job.result_data},
            )

            return job.result_data

        except CircuitBreakerOpenError as exc:
            # Circuit breaker open — service temporarily unavailable, retryable after cooldown
            session.rollback()
            _mark_failed(session, job, "SERVICE_UNAVAILABLE", str(exc), is_retryable=True)
            return {"error": "service_unavailable"}

        except (ClientError, OperationalError) as exc:
            # Transient errors — retry with exponential backoff
            session.rollback()
            job.status = "retrying"
            job.retry_count += 1
            job.last_error_at = _utcnow()
            job.updated_at = _utcnow()
            session.add(job)
            session.commit()

            publish_job_progress(job_id, {
                "event": "job-retrying",
                "jobId": job_id,
                "retryCount": job.retry_count,
                "maxRetries": job.max_retries,
            })

            try:
                self.retry(exc=exc, countdown=2 ** self.request.retries)
            except MaxRetriesExceededError:
                _mark_failed(session, job, "MAX_RETRIES_EXCEEDED", str(exc), is_retryable=True)
                return {"error": "max_retries_exceeded"}

        except UnsupportedFormatError as exc:
            # Permanent non-retryable error
            session.rollback()
            _mark_failed(session, job, "UNSUPPORTED_FORMAT", str(exc), is_retryable=False)
            return {"error": "unsupported_format"}

        except (SoftTimeLimitExceeded, ValueError, KeyError, Exception) as exc:
            # Preserve partial results: commit any transactions added to session
            # before marking the job as failed
            is_retryable = not isinstance(exc, (ValueError, KeyError))
            _commit_partial_and_mark_failed(session, job, exc, job_id, is_retryable=is_retryable)
            if isinstance(exc, SoftTimeLimitExceeded):
                return {"error": "timeout"}
            if isinstance(exc, (ValueError, KeyError)):
                return {"error": "data_error"}
            return {"error": "unknown_error"}


def _commit_partial_and_mark_failed(
    session, job: ProcessingJob, exc: Exception, job_id: str, *, is_retryable: bool = True
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

    _mark_failed(session, job, error_code, error_message, is_retryable=is_retryable)


def _mark_failed(
    session, job: ProcessingJob, error_code: str, error_message: str, *, is_retryable: bool = True
) -> None:
    """Mark a ProcessingJob as failed with error details."""
    job.status = "failed"
    job.error_code = error_code
    job.error_message = error_message
    job.is_retryable = is_retryable
    job.last_error_at = _utcnow()
    job.updated_at = _utcnow()
    session.add(job)
    session.commit()

    publish_job_progress(str(job.id), {
        "event": "job-failed",
        "jobId": str(job.id),
        "status": "failed",
        "error": {"code": error_code, "message": error_message},
        "isRetryable": is_retryable,
    })

    logger.warning(
        "Upload processing failed",
        extra={"job_id": str(job.id), "error_code": error_code, "error_message": error_message},
    )


@celery_app.task(bind=True, max_retries=3, acks_late=True, track_started=True)
def resume_upload(self, job_id: str) -> dict:
    """Resume a failed pipeline job from its last LangGraph checkpoint.

    Called by the retry API endpoint. Uses the job_id as thread_id to
    look up the last checkpoint and resume from the interrupted node.
    """
    with get_sync_session() as session:
        job = session.get(ProcessingJob, uuid.UUID(job_id))
        if job is None:
            logger.error("ProcessingJob not found for resume", extra={"job_id": job_id})
            return {"error": "job_not_found"}

        job.status = "processing"
        job.error_code = None
        job.error_message = None
        job.updated_at = _utcnow()
        session.add(job)
        session.commit()

        publish_job_progress(job_id, {
            "event": "job-resumed",
            "jobId": job_id,
            "resumeFromStep": job.failed_step,
        })

        try:
            with get_checkpointer() as checkpointer:
                result_state = resume_pipeline(checkpointer, thread_id=job_id)

            # Persist any new results from resumed pipeline
            upload_id = uuid.UUID(result_state.get("upload_id", str(job.upload_id)))

            # Update categorization results if present
            cat_lookup = {
                cat["transaction_id"]: cat
                for cat in result_state.get("categorized_transactions", [])
            }
            if cat_lookup:
                txns = session.exec(
                    select(Transaction).where(Transaction.upload_id == upload_id)
                ).all()
                for txn in txns:
                    cat = cat_lookup.get(str(txn.id))
                    if cat and txn.category in (None, "uncategorized"):
                        txn.category = cat["category"]
                        txn.confidence_score = cat["confidence_score"]
                        txn.is_flagged_for_review = cat.get("flagged", False)
                        txn.uncategorized_reason = cat.get("uncategorized_reason")
                        session.add(txn)
                session.commit()

            # Persist insight cards
            insight_cards = result_state.get("insight_cards", [])
            if insight_cards:
                for card in insight_cards:
                    insight = Insight(
                        user_id=job.user_id,
                        upload_id=upload_id,
                        headline=card.get("headline", ""),
                        key_metric=card.get("key_metric", ""),
                        why_it_matters=card.get("why_it_matters", ""),
                        deep_dive=card.get("deep_dive", ""),
                        severity=card.get("severity", "medium"),
                        category=card.get("category", "other"),
                    )
                    session.add(insight)
                session.commit()

            # Build/update financial profile
            try:
                build_or_update_profile(session, job.user_id)
                try:
                    from app.services.health_score_service import calculate_health_score
                    calculate_health_score(session, job.user_id)
                except Exception:
                    logger.warning("Health score calculation failed on resume", extra={"job_id": job_id})
            except Exception:
                logger.warning("Profile build failed on resume", extra={"job_id": job_id})

            # Mark completed
            job.status = "completed"
            job.step = "done"
            job.progress = 100
            job.failed_step = None
            job.updated_at = _utcnow()
            session.add(job)
            session.commit()

            publish_job_progress(job_id, {
                "event": "job-complete",
                "jobId": job_id,
                "status": "completed",
                "totalInsights": len(insight_cards),
            })

            return {"status": "completed", "insight_count": len(insight_cards)}

        except CircuitBreakerOpenError as exc:
            _mark_failed(session, job, "SERVICE_UNAVAILABLE", str(exc), is_retryable=True)
            return {"error": "service_unavailable"}

        except (ClientError, OperationalError) as exc:
            # Transient infrastructure errors — retry with exponential backoff
            session.rollback()
            job.status = "retrying"
            job.retry_count += 1
            job.last_error_at = _utcnow()
            job.updated_at = _utcnow()
            session.add(job)
            session.commit()

            publish_job_progress(job_id, {
                "event": "job-retrying",
                "jobId": job_id,
                "retryCount": job.retry_count,
                "maxRetries": job.max_retries,
            })

            try:
                self.retry(exc=exc, countdown=2 ** self.request.retries)
            except MaxRetriesExceededError:
                _mark_failed(session, job, "MAX_RETRIES_EXCEEDED", str(exc), is_retryable=True)
                return {"error": "max_retries_exceeded"}

        except Exception as exc:
            logger.exception("Resume pipeline failed", extra={"job_id": job_id})
            _commit_partial_and_mark_failed(session, job, exc, job_id, is_retryable=True)
            return {"error": "resume_failed"}
