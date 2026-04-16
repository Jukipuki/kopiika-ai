import logging
import uuid
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import delete as sa_delete
from sqlalchemy import select as sa_select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.audit import anonymize_user_audit_records
from app.core.config import settings
from app.models.consent import UserConsent
from app.models.financial_health_score import FinancialHealthScore
from app.models.financial_profile import FinancialProfile
from app.models.flagged_import_row import FlaggedImportRow
from app.models.insight import Insight
from app.models.processing_job import ProcessingJob
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User
from app.services.cognito_service import CognitoService

logger = logging.getLogger(__name__)


def _get_s3_client():
    return boto3.client("s3", region_name=settings.S3_REGION)


async def get_user_s3_keys(
    session: SQLModelAsyncSession, user_id: uuid.UUID
) -> list[str]:
    result = await session.exec(
        sa_select(Upload.s3_key).where(Upload.user_id == user_id)
    )
    return list(result.scalars().all())


def delete_s3_objects(s3_keys: list[str]) -> None:
    if not s3_keys:
        return
    client = _get_s3_client()
    # S3 delete_objects supports up to 1000 keys per call
    for i in range(0, len(s3_keys), 1000):
        batch = s3_keys[i : i + 1000]
        try:
            client.delete_objects(
                Bucket=settings.S3_UPLOADS_BUCKET,
                Delete={"Objects": [{"Key": k} for k in batch]},
            )
        except ClientError:
            logger.warning(
                "S3 batch delete failed for %d keys, continuing",
                len(batch),
                exc_info=True,
            )


async def delete_all_user_data(
    session: SQLModelAsyncSession,
    user_id: uuid.UUID,
    cognito_sub: str,
    s3_keys: list[str],
    cognito_service: CognitoService,
) -> None:
    import asyncio

    # 1. Explicitly delete child records, then user row
    # CASCADE exists in production, but explicit deletion is more defensive
    child_tables = [
        FlaggedImportRow, Transaction, Insight, ProcessingJob,
        FinancialHealthScore, FinancialProfile, UserConsent, Upload,
    ]
    for model in child_tables:
        await session.exec(sa_delete(model).where(model.user_id == user_id))

    # Anonymize audit records before deleting user — keeps GDPR accountability
    # without retaining the raw cognito_sub (replaced with SHA-256 hash)
    await anonymize_user_audit_records(session, cognito_sub)

    await session.exec(sa_delete(User).where(User.id == user_id))
    await session.commit()

    # 2. Delete S3 objects (after DB commit — if commit fails, files remain intact)
    await asyncio.to_thread(delete_s3_objects, s3_keys)

    # 3. Delete Cognito user
    try:
        cognito_service.delete_user(cognito_sub)
    except Exception:
        logger.warning(
            "Cognito deletion failed after DB deletion, orphan may exist",
            extra={"user_id": str(user_id)},
            exc_info=True,
        )

    # 4. Audit log — user_id + timestamp only, no PII
    logger.info(
        "User data deleted",
        extra={
            "user_id": str(user_id),
            "timestamp": datetime.now(UTC).isoformat(),
            "audit_anonymized": True,
        },
    )
