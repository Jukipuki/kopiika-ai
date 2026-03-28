# Story 2.2: File Validation & Format Detection

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want the system to validate my uploaded files and auto-detect the bank format,
so that I get immediate feedback if something is wrong.

## Acceptance Criteria

1. **Given** I upload a file
   **When** the backend receives it
   **Then** it validates MIME type (CSV or PDF), file size (within limits), and basic format structure before queuing for processing

2. **Given** I upload an unsupported file type (e.g., .xlsx, .jpg)
   **When** validation runs
   **Then** I see a user-friendly error message: specific to the issue (wrong format, too large, etc.) with suggested corrective actions

3. **Given** I upload a CSV file
   **When** the system analyzes the header row and structure
   **Then** it auto-detects the bank format (Monobank, PrivatBank, or unknown) without requiring manual bank selection

4. **Given** all uploaded file content
   **When** it enters the system
   **Then** it is treated as untrusted and sanitized before any further processing

## Tasks / Subtasks

- [x] Task 1: Enhanced File Validation Service (AC: #1, #4)
  - [x] 1.1: Add `charset-normalizer` dependency to `pyproject.toml` for encoding detection
  - [x] 1.2: Extend `upload_service.py` — add magic-byte validation (verify actual file content matches declared MIME type, not just `content_type` header)
  - [x] 1.3: Add CSV structure validation — read first N bytes, detect delimiter (semicolon vs comma), verify at least one header row exists
  - [x] 1.4: Add input sanitization — strip null bytes, validate UTF-8/Windows-1251 decodability, reject files with embedded scripts or binary content in CSV
  - [x] 1.5: Add `detected_format` and `detected_encoding` fields to the `Upload` model via Alembic migration
  - [x] 1.6: Update `processing_jobs.status` to track validation step: "pending" → "validating" → "validated" / "validation_failed"

- [x] Task 2: Bank Format Detection Engine (AC: #3)
  - [x] 2.1: Create `backend/app/services/format_detector.py` — format detection service with registry pattern
  - [x] 2.2: Implement Monobank CSV detection — check for known Monobank header columns (`Дата і час операції`, `Опис операції`, `MCC`, `Сума в валюті картки`, etc.), semicolon delimiter, Windows-1251 encoding
  - [x] 2.3: Implement PrivatBank CSV detection — check for PrivatBank-specific header patterns (different column names, possibly comma-delimited)
  - [x] 2.4: Implement "unknown" fallback — if no known bank pattern matched, detect generic CSV structure (columns, delimiter, encoding) for future extensibility
  - [x] 2.5: Return `FormatDetectionResult` dataclass with: `bank_format` (monobank/privatbank/unknown), `encoding`, `delimiter`, `column_count`, `confidence_score`, `header_row`

- [x] Task 3: Enhanced Error Responses with Actionable Guidance (AC: #2)
  - [x] 3.1: Define granular error codes: `INVALID_FILE_STRUCTURE`, `UNSUPPORTED_BANK_FORMAT`, `ENCODING_ERROR`, `EMPTY_FILE`, `CORRUPTED_FILE` (in addition to existing `INVALID_FILE_TYPE`, `FILE_TOO_LARGE`, `RATE_LIMITED`)
  - [x] 3.2: Add `suggestions` array to error response — each error code maps to user-friendly corrective actions (e.g., "Try re-exporting as CSV from your bank app")
  - [x] 3.3: Update upload endpoint to return format detection results on success: include `detectedFormat`, `encoding`, `columnCount` in the 202 response body
  - [x] 3.4: Add i18n translation keys for new error messages in `en.json` and `uk.json`

- [x] Task 4: Frontend Error Display Enhancement (AC: #2)
  - [x] 4.1: Update `UploadError` type in `types.ts` — add `suggestions: string[]` field
  - [x] 4.2: Update `use-upload.ts` hook — parse new error fields including suggestions
  - [x] 4.3: Update `UploadDropzone.tsx` — display error suggestions as actionable list below the error message
  - [x] 4.4: Add format detection success feedback — show detected bank name (e.g., "Monobank statement detected") after successful validation
  - [x] 4.5: Add i18n translation keys for format feedback and suggestions in `en.json` and `uk.json`

- [x] Task 5: Backend Tests (AC: #1, #2, #3, #4)
  - [x] 5.1: Test magic-byte validation — CSV file with wrong extension, PDF with wrong MIME header, binary file disguised as CSV
  - [x] 5.2: Test format detection — Monobank CSV (Windows-1251, semicolons), PrivatBank CSV, unknown CSV, malformed CSV
  - [x] 5.3: Test encoding detection — Windows-1251, UTF-8, UTF-8-BOM, ISO-8859-1
  - [x] 5.4: Test sanitization — null bytes stripped, embedded script tags rejected, binary content in CSV rejected
  - [x] 5.5: Test error responses — all new error codes return correct messages and suggestions
  - [x] 5.6: Test upload endpoint integration — format detection result included in 202 response

- [x] Task 6: Frontend Tests (AC: #2)
  - [x] 6.1: Test error display with suggestions — render suggestion list, clickable actions
  - [x] 6.2: Test format detection feedback — "Monobank detected" message appears after successful upload
  - [x] 6.3: Regression — all existing upload tests continue to pass

## Dev Notes

### Architecture Compliance

**Tech Stack (MUST use — do NOT introduce alternatives):**
- **Frontend**: Next.js 16.1, TypeScript, Tailwind CSS 4.x, shadcn/ui (CLI v4)
- **Backend**: Python 3.12, FastAPI, SQLModel, Alembic, boto3
- **Database**: PostgreSQL (RDS) — SQLite for tests with aiosqlite
- **Storage**: Amazon S3 with SSE-S3 encryption
- **Testing**: Vitest + React Testing Library (frontend), pytest + httpx (backend)
- **New dependency**: `charset-normalizer` (encoding detection, pure Python, MIT license)

**API Contract — Enhanced Upload Response:**
```
POST /api/v1/uploads
Authorization: Bearer {cognito_jwt}
Content-Type: multipart/form-data
Body: file (CSV or PDF)

Response (202 Accepted):
{
  "jobId": "uuid",
  "statusUrl": "/api/v1/jobs/{jobId}",
  "detectedFormat": "monobank",     // NEW: monobank | privatbank | unknown | null (PDF)
  "encoding": "windows-1251",       // NEW: detected encoding
  "columnCount": 10                  // NEW: number of columns detected
}

Error Response (enhanced):
{
  "error": {
    "code": "UNSUPPORTED_BANK_FORMAT" | "INVALID_FILE_STRUCTURE" | "ENCODING_ERROR" | "EMPTY_FILE" | "CORRUPTED_FILE" | "INVALID_FILE_TYPE" | "FILE_TOO_LARGE" | "RATE_LIMITED",
    "message": "Human-readable message",
    "details": {...},
    "suggestions": [                 // NEW: actionable corrective steps
      "Try re-exporting as CSV from your bank app",
      "Check that the file is a .csv with transaction data"
    ]
  }
}
```

**Database Schema — Migration additions:**
```sql
-- ALTER uploads table
ALTER TABLE uploads ADD COLUMN detected_format VARCHAR(50);   -- monobank, privatbank, unknown, null
ALTER TABLE uploads ADD COLUMN detected_encoding VARCHAR(50); -- windows-1251, utf-8, etc.
```

**Format Detection Pattern — Registry-based:**
```python
# backend/app/services/format_detector.py
class FormatDetectionResult:
    bank_format: str          # "monobank" | "privatbank" | "unknown"
    encoding: str             # "windows-1251" | "utf-8" | etc.
    delimiter: str            # ";" | "," | "\t"
    column_count: int
    confidence_score: float   # 0.0 - 1.0
    header_row: list[str]

class FormatDetector:
    """Registry of bank format detectors. Each detector checks header patterns."""
    def detect(self, file_bytes: bytes) -> FormatDetectionResult: ...
```

**Monobank CSV Header Pattern (known columns, Windows-1251 encoded):**
```
Дата і час операції;Опис операції;MCC;Сума в валюті картки (UAH);Залишок на рахунку (UAH);...
```

### Critical Previous Story Learnings (DO NOT REPEAT THESE BUGS)

1. **DateTime handling**: Use `datetime.now(UTC).replace(tzinfo=None)` for SQLite compatibility — timezone-aware datetimes cause deserialization issues with SQLite
2. **Locale codes**: ISO 639-1 (`"uk"`, `"en"`) — NOT `"ua"`
3. **Data fetching pattern**: Use native `fetch()` with Bearer token from `useSession().accessToken` — do NOT introduce TanStack Query mid-epic (consistency with Stories 1.1-1.7)
4. **Dark mode default**: All new UI components must work with dark theme (#0F1117 bg, #F0F0F3 text, #6C63FF accent)
5. **Font**: DM Sans with `latin + latin-ext` subsets (NOT cyrillic subset)
6. **shadcn/ui**: Components are owned source code in `components/ui/` — use existing Button, Card, Skeleton; add new shadcn components as needed
7. **Feature folder pattern**: `features/upload/{components,hooks,__tests__}/` — builds on existing structure from Story 2.1
8. **i18n pattern**: Namespace-based `useTranslations('upload')`, identical key structure in both `en.json` and `uk.json`
9. **Test mocking**: Use `test-utils/intl-mock.ts` for i18n, mock `useSession()` with `{ accessToken: 'test-token', status: 'authenticated' }`
10. **Accessibility**: WCAG 2.1 AA — semantic HTML, `aria-label`, keyboard nav, 44px min touch targets, 4.5:1 contrast
11. **Environment variables**: Use `|| ""` fallback, NOT `!` assertion — prevents build failures
12. **python-multipart**: Already installed in Story 2.1 for FastAPI UploadFile support
13. **intl-mock**: Doesn't support nested dot-notation keys — use flat key names (e.g., `errorInvalidFileType` not `errors.invalidFileType`)
14. **Pydantic camelCase**: API JSON uses `camelCase` via `alias_generator=to_camel` — DB/Python uses `snake_case`

### UX Implementation Requirements

**Error Handling (Card-based, not modals):**
- Errors displayed inline in the UploadDropzone component (not as modal dialogs)
- User-friendly, non-technical language ONLY
- Each error includes actionable suggestions (3-4 specific steps)
- Lighthearted tone: "Our AI tripped over your spreadsheet — give it another try?" (never clinical, never alarming)

**Format Detection Feedback:**
- On successful validation, show detected bank format: "Monobank statement detected" with a checkmark icon
- Trust messaging reinforced: "Your data stays encrypted and private"

**Error Messages (user-friendly, never technical):**
| Error Code | User Message | Suggestions |
|---|---|---|
| `INVALID_FILE_TYPE` | "Only CSV and PDF files are supported." | "Try exporting your bank statement as CSV." |
| `FILE_TOO_LARGE` | "This file is too large. Please upload files under 10MB." | — |
| `INVALID_FILE_STRUCTURE` | "This file doesn't look like a bank statement." | "Check that the file is a .csv with transaction data", "Try re-exporting from your bank app" |
| `UNSUPPORTED_BANK_FORMAT` | "We couldn't recognize this bank statement format." | "We currently support Monobank CSV", "Try uploading a Monobank statement", "Other banks will be supported soon" |
| `ENCODING_ERROR` | "We had trouble reading this file." | "Try re-exporting the file from your bank", "Make sure the file isn't corrupted" |
| `EMPTY_FILE` | "This file appears to be empty." | "Check that your bank statement has transaction data", "Try downloading the statement again" |
| `CORRUPTED_FILE` | "This file appears to be damaged." | "Try downloading the statement again from your bank" |
| `RATE_LIMITED` | "You've uploaded a lot of files recently." | "Please try again in a few minutes." |

**Animations:**
- `fast` (150ms): Error/success state transitions in upload zone
- `normal` (250ms): Suggestion list appearance, format detection badge

### Library & Framework Requirements

**charset-normalizer (encoding detection):**
- Latest stable: 3.4.x (pure Python, MIT license)
- Usage: `from charset_normalizer import from_bytes; result = from_bytes(file_content).best()`
- Returns detected encoding with confidence score
- Critical for Monobank Windows-1251 detection

**Do NOT introduce:**
- `chardet` (LGPL license concerns, less maintained)
- `python-magic` (requires libmagic system dependency — problematic in Docker/Lambda)
- `google/magika` (AI-powered, overkill for CSV/PDF detection)
- `pandas` for CSV reading (too heavy — use stdlib `csv` module)
- TanStack Query or any new frontend state library

**Use stdlib where possible:**
- `csv.Sniffer()` for delimiter detection
- `csv.reader()` for header row parsing
- `io.BytesIO` / `io.StringIO` for in-memory file processing

### File Structure Requirements

**New files to create:**
```
backend/app/
├── services/
│   └── format_detector.py              # Bank format detection service (NEW)

backend/alembic/versions/
└── xxx_add_format_detection_fields.py   # Migration: detected_format, detected_encoding columns (NEW)
```

**Files to modify:**
```
backend/app/services/upload_service.py   # Enhanced validation + format detection integration
backend/app/api/v1/uploads.py            # Return format detection results in 202 response
backend/app/models/upload.py             # Add detected_format, detected_encoding fields
backend/tests/test_uploads.py            # Add format detection + validation tests
backend/pyproject.toml                   # Add charset-normalizer dependency

frontend/src/features/upload/types.ts    # Add suggestions to UploadError, format detection types
frontend/src/features/upload/hooks/use-upload.ts  # Parse suggestions + format from response
frontend/src/features/upload/components/UploadDropzone.tsx  # Error suggestions + format feedback
frontend/messages/en.json                # New error + format detection keys
frontend/messages/uk.json                # New error + format detection keys
```

### Testing Requirements

**Backend Tests (pytest + httpx) — minimum 12 new test cases:**
- Format detection: Monobank CSV recognized, PrivatBank CSV recognized, unknown CSV handled, non-CSV file handled
- Encoding detection: Windows-1251 detected, UTF-8 detected, UTF-8-BOM handled
- Magic-byte validation: real CSV passes, binary disguised as CSV fails
- Sanitization: null bytes rejected, embedded scripts rejected
- Error responses: all 7 error codes return correct structure with suggestions
- Integration: enhanced 202 response includes format fields

**Frontend Tests (Vitest + React Testing Library) — minimum 4 new test cases:**
- Error suggestions render correctly in UploadDropzone
- Format detection feedback displays (e.g., "Monobank detected")
- Unsupported format error shows specific guidance
- All existing upload tests still pass

**Regression**: All existing tests must continue to pass. Story 2.1 added 21 tests (9 backend + 12 frontend).

**Mock approach**: Create fixture files for tests:
- `tests/fixtures/monobank_sample.csv` — valid Monobank CSV (Windows-1251 encoded, semicolons)
- `tests/fixtures/unknown_bank.csv` — generic CSV that doesn't match any known format
- `tests/fixtures/empty.csv` — empty file
- `tests/fixtures/binary_disguised.csv` — binary content with .csv extension

### Git Intelligence

**Recent commits (most relevant):**
- `0a58b72` Story 2.1: File Upload UI & S3 Storage — established upload infrastructure
- `a379011` Fix DB issues // Fix local switcher on login page — DB fixes applied

**Patterns established:**
- Commit message format: "Story X.Y: Description"
- Code review fixes committed separately with clear descriptions
- Frontend and backend changes in same story commit

### Project Structure Notes

- `upload_service.py` already has basic MIME type and file size validation — extend it, don't rewrite
- `processing_jobs` model already has `status`, `step`, `error_code`, `error_message` fields — reuse for validation status tracking
- `backend/app/agents/ingestion/parsers/` directory does NOT exist yet (architecture planned) — Story 2.2 creates format detection as a service, not as a parser (parsing is Story 2.3)
- Frontend upload feature module fully structured in Story 2.1 — add to existing files, don't restructure
- Rate limiter service reused from Story 2.1 — no changes needed

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 2, Story 2.2]
- [Source: _bmad-output/planning-artifacts/architecture.md — File Processing, Parser Architecture, Validation Layers, API Patterns]
- [Source: _bmad-output/planning-artifacts/prd.md — FR2, FR5, FR37, FR40, Journey 4: Self-Service Error Recovery]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Error & Edge States, File Upload Error Flow, Error State Emotional Design]
- [Source: _bmad-output/implementation-artifacts/2-1-file-upload-ui-s3-storage.md — Previous Story Patterns, File Structure, Debug Learnings]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Fixed pre-existing test failure in `test_tenant_isolation.py::test_alembic_migration_file_exists_and_correct` — the test assumed alphabetical first migration has `down_revision=None`, but Story 2.1's migration (`4c94b3ca32be_...`) sorts before the initial migration (`feb18f356210_...`). Fixed to scan for the initial migration by `down_revision is None` instead of relying on alphabetical order.
- Fixed Monobank format detection: real Monobank CSV exports use different column names than documented (e.g., `Дата i час операції` with Latin `i`, `Деталі операції` instead of `Опис операції`), comma delimiters, quoted fields, and UTF-8 encoding — not semicolons/Windows-1251 as the story spec assumed. Switched from exact column matching to substring fingerprinting (`MCC`, `валюті картки`, `кешбек`) to handle evolving export formats.
- Fixed settings page locale switch bug: `router.replace(pathname, { locale })` from next-intl does soft client-side navigation that doesn't trigger middleware or reset locale context, causing URL doubling (`/en/en/settings`). Replaced with `window.location.href` full navigation — same pattern already used by `LocaleSwitcher` component. **LEARNING: Always use `window.location.href` for locale switching in this project, never `router.replace` with locale option.**

### Completion Notes List

- Implemented full file validation pipeline: magic-byte validation, CSV structure validation, input sanitization (null bytes, script injection)
- Created bank format detection engine with registry pattern: Monobank (Windows-1251, semicolons), PrivatBank (UTF-8, commas), and unknown fallback
- Used `charset-normalizer` for encoding detection, stdlib `csv.Sniffer()` for delimiter detection
- Enhanced error responses with `suggestions` array for all validation error codes
- Upload endpoint now returns `detectedFormat`, `encoding`, `columnCount` in 202 response
- Frontend displays error suggestions as actionable list and shows format detection feedback ("Monobank statement detected")
- Added Alembic migration for `detected_format` and `detected_encoding` columns on uploads table
- ProcessingJob initial status changed from "pending" to "validating" to reflect validation step
- Backend: 29 new tests (all pass), 9 existing tests (all pass, 1 updated for status change)
- Frontend: 16 new tests (all pass), 12 existing tests (all pass, 1 updated for error message change)
- Full regression: 83/83 backend tests pass (fixed 1 pre-existing failure), 86/86 frontend tests pass

### Change Log

- 2026-03-28: Story 2.2 implementation — file validation, format detection, enhanced error responses, frontend display updates
- 2026-03-28: Fix Monobank detection — switched to fingerprint matching for real export format compatibility
- 2026-03-28: Fix settings locale switch — replaced `router.replace` with `window.location.href` to prevent URL doubling
- 2026-03-28: Code review fixes — internationalized suggestions (i18n keys instead of raw strings), fixed ProcessingJob status to "validated", removed suggestion duplication in error responses, added ISO-8859-1 encoding test, added UNAUTHENTICATED error mapping, refactored encoding detection to single call per upload, documented UNSUPPORTED_BANK_FORMAT as reserved, documented Alembic migration ID mismatch

### File List

**New files:**
- backend/app/services/format_detector.py
- backend/alembic/versions/f3a8b2c1d4e5_add_format_detection_fields.py
- backend/tests/test_format_detection.py
- backend/tests/fixtures/monobank_sample.csv
- backend/tests/fixtures/unknown_bank.csv
- backend/tests/fixtures/empty.csv
- backend/tests/fixtures/binary_disguised.csv
- backend/tests/fixtures/monobank_modern.csv

**Modified files:**
- backend/pyproject.toml
- backend/app/services/upload_service.py
- backend/app/api/v1/uploads.py
- backend/app/models/upload.py
- backend/app/core/exceptions.py
- backend/tests/test_uploads.py
- backend/tests/test_tenant_isolation.py
- frontend/src/features/upload/types.ts
- frontend/src/features/upload/hooks/use-upload.ts
- frontend/src/features/upload/components/UploadDropzone.tsx
- frontend/messages/en.json
- frontend/messages/uk.json
- frontend/src/features/upload/__tests__/UploadDropzone.test.tsx
- frontend/src/features/upload/__tests__/use-upload.test.tsx
- frontend/src/features/settings/components/LanguageSection.tsx
- frontend/src/features/settings/__tests__/SettingsPage.test.tsx
- backend/uv.lock
