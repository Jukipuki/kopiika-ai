"""Privacy-consent version constants and related metadata.

IMPORTANT — READ BEFORE EDITING:

There are TWO independent consent streams, each with its OWN version
constant. Bumping one MUST NOT bump the other.

- ``CURRENT_CONSENT_VERSION`` (``ai_processing``) — covers the batch
  pipeline: ingestion, categorization, education, profile, feedback. This
  consent is granted during onboarding and is revoked only by full account
  deletion (Story 5.5).
- ``CURRENT_CHAT_CONSENT_VERSION`` (``chat_processing``) — covers the
  conversational surface: conversation logging, cross-session memory,
  retention window, and use of anonymized conversation signals for
  chat-quality improvement. Granted on first chat use (Story 10.3b / 10.7),
  revocable independently via ``DELETE /users/me/consent?type=chat_processing``.

Bump either constant ONLY when the privacy text for that scope materially
changes (new data flows, new processors, new data categories). Cosmetic
copy edits must NOT bump — bumping forces every user back through the
corresponding consent screen on next use, which is user-hostile.

These constants have mirrors in the frontend at
``frontend/src/features/onboarding/consent-version.ts`` — both files must
move together. A CI contract check (see
``.github/workflows/consent-version-sync.yml``) fails builds where either
constant drifts out of sync between backend and frontend.

Format: date-prefixed string ``YYYY-MM-DD-vN`` (matches the repo convention
for migration filenames and retrospective filenames; keeps the audit trail
human-readable).
"""

from typing import Final

CURRENT_CONSENT_VERSION: Final[str] = "2026-04-11-v1"
CONSENT_TYPE_AI_PROCESSING: Final[str] = "ai_processing"

CURRENT_CHAT_CONSENT_VERSION: Final[str] = "2026-04-24-v1"
CONSENT_TYPE_CHAT_PROCESSING: Final[str] = "chat_processing"
