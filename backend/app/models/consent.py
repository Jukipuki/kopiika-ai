import uuid
from datetime import UTC, datetime

from sqlmodel import Field, Index, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class UserConsent(SQLModel, table=True):
    """Append-only audit log of user consent grants.

    Every grant creates a new row. Rows are NEVER updated or deleted by the
    application — deletion only happens via ON DELETE CASCADE from the users
    table (handled by Story 5.5 "Delete All My Data"). Bumping the
    CURRENT_CONSENT_VERSION constant forces every user back through the
    onboarding screen and produces a new row on next login.
    """

    __tablename__ = "user_consents"
    __table_args__ = (
        Index(
            "ix_user_consents_user_id_consent_type_version",
            "user_id",
            "consent_type",
            "version",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
    )
    consent_type: str = Field(default="ai_processing", index=True, nullable=False)
    version: str = Field(index=True, nullable=False)
    # ``granted_at`` vs ``revoked_at`` are mutually-exclusive event-type
    # discriminators: exactly one is non-NULL per row. Grant helpers set
    # ``granted_at`` explicitly; revoke helpers pass ``None``. A DB-side
    # ``DEFAULT now()`` (M4 fix, migration d8a0f2c4e6b9) is installed as a
    # safety net for any INSERT path that omits the column — it is
    # intentionally NOT mirrored on the SQLModel ``Field`` here because
    # SQLAlchemy would then treat ``None`` as "use default" and the DB
    # default would fire for revoke rows (which must persist NULL).
    # Deterministic ordering under same-microsecond ties is provided by
    # secondary ``ORDER BY id`` in consumers of this table.
    granted_at: datetime | None = Field(default=None, nullable=True)
    locale: str = Field(nullable=False)
    ip: str | None = Field(default=None)
    user_agent: str | None = Field(default=None)
    # Revocation marker — only ever set on a *new* row inserted to represent
    # a revocation event. Grant rows (including all `ai_processing` rows)
    # keep this NULL. Preserves the append-only invariant.
    revoked_at: datetime | None = Field(default=None, nullable=True)
