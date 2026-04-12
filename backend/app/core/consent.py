"""Privacy-consent version constants and related metadata.

IMPORTANT — READ BEFORE EDITING:

CURRENT_CONSENT_VERSION identifies the privacy-explanation *content* users
agreed to. It has NO relationship to app version, API version, or release
version. Bump it ONLY when the privacy text materially changes (new data
flows, new processors, new data categories). Cosmetic copy edits must NOT
bump it — bumping it forces every user back through the onboarding gate on
their next login, which is user-hostile.

This constant has a mirror in the frontend at
``frontend/src/features/onboarding/consent-version.ts`` — both files must
move together. A CI contract check (see
``.github/workflows/consent-version-sync.yml``) fails builds where the two
drift out of sync.

Format: date-prefixed string ``YYYY-MM-DD-vN`` (matches the repo convention
for migration filenames and retrospective filenames; keeps the audit trail
human-readable).
"""

from typing import Final

CURRENT_CONSENT_VERSION: Final[str] = "2026-04-11-v1"
CONSENT_TYPE_AI_PROCESSING: Final[str] = "ai_processing"
