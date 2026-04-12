/**
 * Frontend mirror of ``backend/app/core/consent.py:CURRENT_CONSENT_VERSION``.
 *
 * IMPORTANT — READ BEFORE EDITING:
 *
 * This constant identifies the privacy-explanation *content* users agreed
 * to. It has NO relationship to app version, API version, or release
 * version. Bump it ONLY when the privacy text materially changes (new data
 * flows, new processors, new data categories). Cosmetic copy edits must NOT
 * bump it — bumping forces every user back through the onboarding gate on
 * next login, which is user-hostile.
 *
 * This value MUST stay in sync with the backend constant at
 * ``backend/app/core/consent.py``. A CI guardrail
 * (``.github/workflows/consent-version-sync.yml``) fails builds where the
 * two drift out of sync.
 *
 * Format: date-prefixed string ``YYYY-MM-DD-vN``.
 */
export const CURRENT_CONSENT_VERSION = "2026-04-11-v1";

export const CONSENT_TYPE_AI_PROCESSING = "ai_processing";
