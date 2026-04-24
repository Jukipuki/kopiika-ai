/**
 * Frontend mirror of ``backend/app/core/consent.py`` version constants.
 *
 * IMPORTANT — READ BEFORE EDITING:
 *
 * There are TWO independent consent streams, each with its OWN version
 * constant. Bumping one MUST NOT bump the other.
 *
 * - ``CURRENT_CONSENT_VERSION`` (``ai_processing``) — covers the batch
 *   pipeline (ingestion, categorization, education, profile, feedback).
 *   Granted during onboarding; revoked only by full account deletion.
 * - ``CURRENT_CHAT_CONSENT_VERSION`` (``chat_processing``) — covers the
 *   conversational surface: conversation logging, cross-session memory,
 *   retention window, and anonymized chat-quality signals. Granted on
 *   first chat use, revocable independently.
 *
 * Bump either constant ONLY when the privacy text materially changes.
 * Cosmetic copy edits must NOT bump — bumping forces every user back
 * through the corresponding consent screen on next use.
 *
 * These values MUST stay in sync with the backend constants in
 * ``backend/app/core/consent.py``. A CI guardrail
 * (``.github/workflows/consent-version-sync.yml``) fails builds where
 * either constant drifts out of sync.
 *
 * Format: date-prefixed string ``YYYY-MM-DD-vN``.
 */
export const CURRENT_CONSENT_VERSION = "2026-04-11-v1";

export const CONSENT_TYPE_AI_PROCESSING = "ai_processing";

export const CURRENT_CHAT_CONSENT_VERSION = "2026-04-24-v1";

export const CONSENT_TYPE_CHAT_PROCESSING = "chat_processing";
