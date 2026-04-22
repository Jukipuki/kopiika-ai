import logging
import time
import uuid
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded
from sqlalchemy.exc import OperationalError
from sqlmodel import func, select

from app.agents.categorization.node import kind_by_sign, validate_kind_category
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
from app.models.uncategorized_review_queue import UncategorizedReviewQueue
from app.models.upload import Upload
from app.models.user import User
from app.services.format_detector import (
    FormatDetectionResult,
    get_bank_display_name,
    get_sign_convention,
)
from app.services.parser_service import (
    UnsupportedFormatError,
    WholesaleRejectionError,
    sync_parse_and_store_transactions,
)
from app.services.profile_service import build_or_update_profile
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _maybe_build_review_queue_entry(
    *, cat: dict, txn: Transaction
) -> UncategorizedReviewQueue | None:
    """Return a queue entry for a low-confidence row if one is warranted.

    Story 11.8 AC #4: route rows with ``uncategorized_reason='low_confidence'``
    AND a non-null LLM suggestion into the review queue. Infrastructure-failure
    flags (``llm_unavailable``, ``parse_failure``, ``currency_unknown``) are
    skipped — they have no suggestion for the user to act on.
    """
    if cat.get("uncategorized_reason") != "low_confidence":
        return None
    suggested_category = cat.get("suggested_category")
    suggested_kind = cat.get("suggested_kind")
    if not suggested_category or not suggested_kind:
        return None
    return UncategorizedReviewQueue(
        user_id=txn.user_id,
        transaction_id=txn.id,
        categorization_confidence=cat["confidence_score"],
        suggested_category=suggested_category,
        suggested_kind=suggested_kind,
        status="pending",
    )


def _existing_queue_txn_ids(
    session, txn_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    """Return the subset of `txn_ids` that already have ANY queue row.

    Used to dedup queue inserts on ``resume_upload`` (which re-runs the
    categorization pipeline against transactions that may already have been
    queued on the first pass). Queries for any status — a row that was
    already resolved/dismissed shouldn't be re-queued either.
    """
    if not txn_ids:
        return set()
    rows = session.exec(
        select(UncategorizedReviewQueue.transaction_id).where(
            UncategorizedReviewQueue.transaction_id.in_(txn_ids),
        )
    ).all()
    return set(rows)


def _build_state_transactions(
    transactions_for_pipeline, session, user_id: uuid.UUID
) -> list[dict]:
    """Build the state.transactions list, pre-computing per-row counterparty signals.

    Story 11.10: `is_self_iban` is resolved ONCE here against `user_iban_registry`
    so the categorization node does not touch the DB inside its prompt-retry loop.
    `counterparty_tax_id_kind` is a cheap deterministic classification (no DB).
    """
    from app.agents.categorization.counterparty_patterns import edrpou_kind
    from app.services.user_iban_registry import UserIbanRegistryService

    svc = UserIbanRegistryService(session)
    out: list[dict] = []
    for t in transactions_for_pipeline:
        is_self_iban = False
        if t.counterparty_account:
            try:
                is_self_iban = svc.is_user_iban(user_id, t.counterparty_account)
            except Exception as exc:  # DB schema drift / eager lookup failure
                logger.warning(
                    "user_iban_registry.lookup_failed",
                    extra={"user_id": str(user_id), "error": str(exc)},
                )
        out.append(
            {
                "id": str(t.id),
                "mcc": t.mcc,
                "description": t.description,
                "amount": t.amount,
                "date": str(t.date),
                "counterparty_name": t.counterparty_name,
                "counterparty_tax_id": t.counterparty_tax_id,
                "counterparty_account": t.counterparty_account,
                "counterparty_tax_id_kind": edrpou_kind(t.counterparty_tax_id),
                "is_self_iban": is_self_iban,
            }
        )
    return out


def _get_upload_summary(session, upload_id: uuid.UUID) -> tuple[str | None, str | None]:
    """Compute (date_range_start, date_range_end) ISO date strings for an upload's transactions.

    Returns ISO 8601 date strings (YYYY-MM-DD) — the time component is dropped
    even though Transaction.date is a datetime column, since the summary is
    user-facing and only the calendar date matters.

    Returns (None, None) when the upload has no persisted transactions.
    """
    min_date, max_date = session.exec(
        select(func.min(Transaction.date), func.max(Transaction.date))
        .where(Transaction.upload_id == upload_id)
    ).one()
    if min_date and max_date:
        return min_date.date().isoformat(), max_date.date().isoformat()
    return None, None


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
        job.started_at = _utcnow()
        job.updated_at = _utcnow()
        session.add(job)
        session.commit()

        task_start = time.monotonic()
        ingestion_ms = None
        categorization_ms = None
        education_ms = None

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

            # --- Ingestion timing start ---
            ingestion_start = time.monotonic()

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
                amount_sign_convention=get_sign_convention(upload.detected_format),
            )

            # 6. Parse and store transactions
            result = sync_parse_and_store_transactions(
                session=session,
                user_id=job.user_id,
                upload_id=upload.id,
                file_bytes=file_bytes,
                format_result=format_result,
            )

            ingestion_ms = round((time.monotonic() - ingestion_start) * 1000)
            # --- Ingestion timing end ---

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

            # --- Categorization timing start ---
            categorization_start = time.monotonic()

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
                    "transactions": _build_state_transactions(
                        transactions_for_pipeline, session, job.user_id,
                    ),
                    "categorized_transactions": [],
                    "errors": [],
                    "step": "categorization",
                    "total_tokens_used": 0,
                    "locale": locale,
                    "insight_cards": [],
                    "literacy_level": literacy_level,
                    "completed_nodes": [],
                    "failed_node": None,
                    "pattern_findings": [],
                    "detected_subscriptions": [],
                    "triage_category_severity_map": {},
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
                queue_entries: list[UncategorizedReviewQueue] = []
                already_queued = _existing_queue_txn_ids(
                    session, [t.id for t in txns]
                )
                for txn in txns:
                    cat = cat_lookup.get(str(txn.id))
                    if cat:
                        category = cat["category"]
                        kind = cat.get("transaction_kind", "spending")
                        confidence = cat["confidence_score"]
                        mismatch = not validate_kind_category(kind, category)
                        if mismatch:
                            # Spec §2.3 fallback: invalid (kind, category) pair →
                            # (uncategorized, <by-sign>, confidence=0.0). Chosen over
                            # raising so one bad LLM pair doesn't abort the whole upload.
                            logger.warning(
                                "categorization.kind_mismatch",
                                extra={
                                    "job_id": job_id,
                                    "user_id": str(job.user_id),
                                    "tx_id": str(txn.id),
                                    "returned_kind": kind,
                                    "returned_category": category,
                                },
                            )
                            category = "uncategorized"
                            kind = kind_by_sign(txn.amount)
                            confidence = 0.0
                        txn.category = category
                        txn.confidence_score = confidence
                        txn.transaction_kind = kind
                        # Preserve parser-side pre-flag (e.g. currency_unknown).
                        if txn.uncategorized_reason is None:
                            if mismatch:
                                txn.is_flagged_for_review = True
                                txn.uncategorized_reason = "kind_category_mismatch"
                            else:
                                txn.is_flagged_for_review = cat.get("flagged", False)
                                txn.uncategorized_reason = cat.get("uncategorized_reason")
                        session.add(txn)
                        if not mismatch and txn.id not in already_queued:
                            entry = _maybe_build_review_queue_entry(cat=cat, txn=txn)
                            if entry is not None:
                                session.add(entry)
                                queue_entries.append(entry)
                                already_queued.add(txn.id)
                session.commit()
                # Story 11.8 AC #10: emit review_queue_insert *after* the commit,
                # so failed rollbacks don't pollute the telemetry.
                for entry in queue_entries:
                    logger.info(
                        "categorization.review_queue_insert",
                        extra={
                            "job_id": job_id,
                            "upload_id": str(upload.id),
                            "user_id": str(entry.user_id),
                            "transaction_id": str(entry.transaction_id),
                            "categorization_confidence": entry.categorization_confidence,
                            "suggested_category": entry.suggested_category,
                            "suggested_kind": entry.suggested_kind,
                        },
                    )

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
                            severity=card.get("severity", "info"),
                            category=card.get("category", "other"),
                            card_type=card.get("card_type", "insight"),
                            subscription_json=card.get("subscription"),
                        )
                        session.add(insight)
                        insights.append(insight)
                    session.commit()

                publish_job_progress(job_id, {
                    "event": "pipeline-progress",
                    "jobId": job_id,
                    "step": "insights",
                    "progress": 70,
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

            categorization_ms = round((time.monotonic() - categorization_start) * 1000)
            # --- Categorization timing end ---

            # --- Education/profile timing start ---
            education_start = time.monotonic()

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

            education_ms = round((time.monotonic() - education_start) * 1000)
            # --- Education/profile timing end ---

            total_ms = round((time.monotonic() - task_start) * 1000)
            agent_timings = {
                "ingestion_ms": ingestion_ms,
                "categorization_ms": categorization_ms,
                "education_ms": education_ms,
            }

            # 10. Compute upload summary for completion payload
            bank_name = get_bank_display_name(upload.detected_format)
            date_range_start, date_range_end = _get_upload_summary(session, upload.id)
            insight_count = len(insight_cards)
            date_range = (
                {"start": date_range_start, "end": date_range_end}
                if date_range_start and date_range_end
                else None
            )

            # 11. Update ProcessingJob to "completed"
            job.status = "completed"
            if job.step != "categorization_failed":
                job.step = "done"
            job.progress = 100
            # Story 11.7: the parser_service layer now reports the actual
            # source path (known/cached/llm/fallback). Derivation from
            # detected_format is no longer accurate for unknown formats.
            schema_detection_source = result.schema_detection_source
            job.result_data = {
                "total_rows": result.total_rows,
                "parsed_count": result.parsed_count,
                "flagged_count": result.flagged_count,
                "persisted_count": result.persisted_count,
                "duplicates_skipped": result.duplicates_skipped,
                "categorization_count": categorization_count,
                "flagged_count_categorization": flagged_count_categorization,
                "total_tokens_used": total_tokens_used,
                "agent_timings": agent_timings,
                "total_ms": total_ms,
                "bank_name": bank_name,
                "date_range_start": date_range_start,
                "date_range_end": date_range_end,
                "insight_count": insight_count,
                "new_transactions": new_transactions,
                "rejected_rows": result.rejected_rows,
                "warnings": result.warnings,
                "schema_detection_source": schema_detection_source,
                "mojibake_detected": result.mojibake_detected,
            }

            if result.mojibake_detected:
                logger.warning(
                    "parser.mojibake_detected",
                    extra={
                        "upload_id": str(upload.id),
                        "encoding": format_result.encoding,
                        "replacement_char_rate": result.mojibake_replacement_rate,
                    },
                )

            job.updated_at = _utcnow()
            session.add(job)
            session.commit()

            publish_job_progress(job_id, {
                "event": "job-complete",
                "jobId": job_id,
                "status": "completed",
                "duplicatesSkipped": result.duplicates_skipped,
                "newTransactions": new_transactions,
                "totalInsights": insight_count,
                "bankName": bank_name,
                "transactionCount": new_transactions,
                "dateRange": date_range,
                "rejectedRows": result.rejected_rows,
                "warnings": result.warnings,
                "schemaDetectionSource": schema_detection_source,
                "mojibakeDetected": result.mojibake_detected,
            })

            logger.info(
                "pipeline_completed",
                extra={
                    "job_id": job_id,
                    "upload_id": str(upload.id),
                    "user_id": str(upload.user_id),
                    "file_size": upload.file_size,
                    "file_type": upload.mime_type,
                    "bank_format_detected": upload.detected_format,
                    "status": "completed",
                    "ingestion_ms": ingestion_ms,
                    "categorization_ms": categorization_ms,
                    "education_ms": education_ms,
                    "total_ms": total_ms,
                    "total_rows": result.total_rows,
                    "categorization_count": categorization_count,
                },
            )

            return job.result_data

        except CircuitBreakerOpenError as exc:
            # Circuit breaker open — service temporarily unavailable, retryable after cooldown
            session.rollback()
            partial = _collect_partial_timings(ingestion_ms, categorization_ms, education_ms)
            _mark_failed(session, job, "SERVICE_UNAVAILABLE", str(exc), is_retryable=True, timings=partial)
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
                partial = _collect_partial_timings(ingestion_ms, categorization_ms, education_ms)
                _mark_failed(session, job, "MAX_RETRIES_EXCEEDED", str(exc), is_retryable=True, timings=partial)
                return {"error": "max_retries_exceeded"}

        except UnsupportedFormatError as exc:
            # Permanent non-retryable error
            session.rollback()
            partial = _collect_partial_timings(ingestion_ms, categorization_ms, education_ms)
            _mark_failed(session, job, "UNSUPPORTED_FORMAT", str(exc), is_retryable=False, timings=partial)
            return {"error": "unsupported_format"}

        except WholesaleRejectionError as exc:
            # Validation rejected the entire parser output (e.g. suspicious_duplicate_rate).
            # Non-retryable — the file is the root cause; user must re-export.
            session.rollback()
            partial = _collect_partial_timings(ingestion_ms, categorization_ms, education_ms)
            _mark_failed(
                session, job, "WHOLESALE_REJECTION", exc.reason,
                is_retryable=False, timings=partial,
            )
            return {"error": "wholesale_rejection", "reason": exc.reason}

        except (SoftTimeLimitExceeded, ValueError, KeyError, Exception) as exc:
            # Preserve partial results: commit any transactions added to session
            # before marking the job as failed
            is_retryable = not isinstance(exc, (ValueError, KeyError))
            partial = _collect_partial_timings(ingestion_ms, categorization_ms, education_ms)
            _commit_partial_and_mark_failed(session, job, exc, job_id, is_retryable=is_retryable, timings=partial)
            if isinstance(exc, SoftTimeLimitExceeded):
                return {"error": "timeout"}
            if isinstance(exc, (ValueError, KeyError)):
                return {"error": "data_error"}
            return {"error": "unknown_error"}


def _collect_partial_timings(
    ingestion_ms: int | None,
    categorization_ms: int | None,
    education_ms: int | None,
) -> dict | None:
    """Build a partial timings dict from whatever stages completed before failure."""
    timings = {}
    if ingestion_ms is not None:
        timings["ingestion_ms"] = ingestion_ms
    if categorization_ms is not None:
        timings["categorization_ms"] = categorization_ms
    if education_ms is not None:
        timings["education_ms"] = education_ms
    return timings or None


def _commit_partial_and_mark_failed(
    session, job: ProcessingJob, exc: Exception, job_id: str,
    *, is_retryable: bool = True, timings: dict | None = None,
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

    _mark_failed(session, job, error_code, error_message, is_retryable=is_retryable, timings=timings)


def _mark_failed(
    session, job: ProcessingJob, error_code: str, error_message: str,
    *, is_retryable: bool = True, timings: dict | None = None,
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

    # Emit pipeline_metrics log for failure tracking
    try:
        upload = session.get(Upload, job.upload_id) if job.upload_id else None
        logger.info(
            "pipeline_metrics",
            extra={
                "job_id": str(job.id),
                "upload_id": str(job.upload_id),
                "user_id": str(job.user_id),
                "file_size": upload.file_size if upload else None,
                "file_type": upload.mime_type if upload else None,
                "bank_format_detected": upload.detected_format if upload else None,
                "status": "failed",
                "error_type": error_code,
                "partial_timings": timings,
            },
        )
    except Exception:
        logger.warning("Failed to emit pipeline_metrics log", extra={"job_id": str(job.id)})


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
        job.started_at = _utcnow()
        job.updated_at = _utcnow()
        session.add(job)
        session.commit()

        task_start = time.monotonic()
        categorization_ms = None
        education_ms = None

        publish_job_progress(job_id, {
            "event": "job-resumed",
            "jobId": job_id,
            "resumeFromStep": job.failed_step,
        })

        try:
            # --- Categorization timing start ---
            categorization_start = time.monotonic()

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
                queue_entries: list[UncategorizedReviewQueue] = []
                already_queued = _existing_queue_txn_ids(
                    session, [t.id for t in txns]
                )
                for txn in txns:
                    cat = cat_lookup.get(str(txn.id))
                    if cat and txn.category in (None, "uncategorized"):
                        category = cat["category"]
                        kind = cat.get("transaction_kind", "spending")
                        confidence = cat["confidence_score"]
                        mismatch = not validate_kind_category(kind, category)
                        if mismatch:
                            logger.warning(
                                "categorization.kind_mismatch",
                                extra={
                                    "job_id": job_id,
                                    "user_id": str(job.user_id),
                                    "tx_id": str(txn.id),
                                    "returned_kind": kind,
                                    "returned_category": category,
                                },
                            )
                            category = "uncategorized"
                            kind = kind_by_sign(txn.amount)
                            confidence = 0.0
                        txn.category = category
                        txn.confidence_score = confidence
                        txn.transaction_kind = kind
                        # Preserve parser-side pre-flag (e.g. currency_unknown).
                        if txn.uncategorized_reason is None:
                            if mismatch:
                                txn.is_flagged_for_review = True
                                txn.uncategorized_reason = "kind_category_mismatch"
                            else:
                                txn.is_flagged_for_review = cat.get("flagged", False)
                                txn.uncategorized_reason = cat.get("uncategorized_reason")
                        session.add(txn)
                        if not mismatch and txn.id not in already_queued:
                            entry = _maybe_build_review_queue_entry(cat=cat, txn=txn)
                            if entry is not None:
                                session.add(entry)
                                queue_entries.append(entry)
                                already_queued.add(txn.id)
                session.commit()
                for entry in queue_entries:
                    logger.info(
                        "categorization.review_queue_insert",
                        extra={
                            "job_id": job_id,
                            "upload_id": str(upload_id),
                            "user_id": str(entry.user_id),
                            "transaction_id": str(entry.transaction_id),
                            "categorization_confidence": entry.categorization_confidence,
                            "suggested_category": entry.suggested_category,
                            "suggested_kind": entry.suggested_kind,
                        },
                    )

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
                        severity=card.get("severity", "info"),
                        category=card.get("category", "other"),
                        card_type=card.get("card_type", "insight"),
                        subscription_json=card.get("subscription"),
                    )
                    session.add(insight)
                session.commit()

            categorization_ms = round((time.monotonic() - categorization_start) * 1000)
            # --- Categorization timing end ---

            # --- Education/profile timing start ---
            education_start = time.monotonic()

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

            education_ms = round((time.monotonic() - education_start) * 1000)
            # --- Education/profile timing end ---

            total_ms = round((time.monotonic() - task_start) * 1000)
            agent_timings = {
                "categorization_ms": categorization_ms,
                "education_ms": education_ms,
            }

            # Compute upload summary for resumed completion payload
            upload_for_summary = session.get(Upload, upload_id)
            bank_name = (
                get_bank_display_name(upload_for_summary.detected_format)
                if upload_for_summary
                else None
            )
            date_range_start, date_range_end = _get_upload_summary(session, upload_id)
            # On resume, education may add new insight cards; combine with prior count
            prior_insight_count = (job.result_data or {}).get("insight_count", 0) if job.result_data else 0
            insight_count = prior_insight_count + len(insight_cards)
            new_transactions = (job.result_data or {}).get("new_transactions") if job.result_data else None
            duplicates_skipped = (job.result_data or {}).get("duplicates_skipped") if job.result_data else None
            date_range = (
                {"start": date_range_start, "end": date_range_end}
                if date_range_start and date_range_end
                else None
            )

            # Mark completed
            job.status = "completed"
            job.step = "done"
            job.progress = 100
            job.failed_step = None
            job.result_data = {
                **(job.result_data or {}),
                "agent_timings": agent_timings,
                "total_ms": total_ms,
                "bank_name": bank_name,
                "date_range_start": date_range_start,
                "date_range_end": date_range_end,
                "insight_count": insight_count,
            }
            job.updated_at = _utcnow()
            session.add(job)
            session.commit()

            prior_result = job.result_data or {}
            publish_job_progress(job_id, {
                "event": "job-complete",
                "jobId": job_id,
                "status": "completed",
                "totalInsights": insight_count,
                "bankName": bank_name,
                "transactionCount": new_transactions,
                "dateRange": date_range,
                "duplicatesSkipped": duplicates_skipped,
                "newTransactions": new_transactions,
                "rejectedRows": prior_result.get("rejected_rows", []),
                "warnings": prior_result.get("warnings", []),
                "schemaDetectionSource": prior_result.get("schema_detection_source", "known_bank_parser"),
                "mojibakeDetected": prior_result.get("mojibake_detected", False),
            })

            upload = session.get(Upload, job.upload_id)
            logger.info(
                "pipeline_completed",
                extra={
                    "job_id": job_id,
                    "upload_id": str(job.upload_id),
                    "user_id": str(job.user_id),
                    "file_size": upload.file_size if upload else None,
                    "file_type": upload.mime_type if upload else None,
                    "bank_format_detected": upload.detected_format if upload else None,
                    "status": "resumed_completed",
                    "categorization_ms": categorization_ms,
                    "education_ms": education_ms,
                    "total_ms": total_ms,
                    "total_rows": prior_result.get("total_rows", 0),
                    "categorization_count": prior_result.get("categorization_count", 0),
                },
            )

            return {"status": "completed", "insight_count": len(insight_cards)}

        except CircuitBreakerOpenError as exc:
            session.rollback()
            partial = _collect_partial_timings(None, categorization_ms, education_ms)
            _mark_failed(session, job, "SERVICE_UNAVAILABLE", str(exc), is_retryable=True, timings=partial)
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
                partial = _collect_partial_timings(None, categorization_ms, education_ms)
                _mark_failed(session, job, "MAX_RETRIES_EXCEEDED", str(exc), is_retryable=True, timings=partial)
                return {"error": "max_retries_exceeded"}

        except Exception as exc:
            logger.exception("Resume pipeline failed", extra={"job_id": job_id})
            session.rollback()
            partial = _collect_partial_timings(None, categorization_ms, education_ms)
            _commit_partial_and_mark_failed(session, job, exc, job_id, is_retryable=True, timings=partial)
            return {"error": "resume_failed"}
