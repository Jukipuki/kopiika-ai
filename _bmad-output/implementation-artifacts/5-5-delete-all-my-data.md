# Story 5.5: Delete All My Data

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to delete all my data with a single action,
So that I can exercise my right to be forgotten.

## Acceptance Criteria

1. **Given** I am on the "My Data" section in settings, **When** I click "Delete All My Data", **Then** I see a confirmation dialog warning that this action is permanent and irreversible
2. **Given** I confirm the deletion, **When** the system processes it, **Then** all data is deleted: user account, transactions, uploads (S3 files), embeddings (pgvector — user-scoped only, NOT RAG corpus), financial profile, Health Score history, insights, and consent records — via cascading delete
3. **Given** the deletion is complete, **When** the process finishes, **Then** I am logged out and redirected to the landing page with a confirmation message
4. **Given** another user's data exists in the system, **When** my data is deleted, **Then** no other user's data is affected (tenant isolation preserved)
5. **Given** a deletion request, **When** it is processed, **Then** the operation is logged for audit purposes (user_id + timestamp only, no personal data retained)

## Tasks / Subtasks

- [x] Task 1: Add `admin_delete_user` method to CognitoService (AC: #2)
  - [x] 1.1 Add `delete_user(cognito_sub: str) -> dict` method to `backend/app/services/cognito_service.py` — calls `self._client.admin_delete_user(UserPoolId=self._user_pool_id, Username=cognito_sub)`
  - [x] 1.2 Handle `ClientError` with appropriate error mapping (UserNotFoundException → already deleted, generic → 500)

- [x] Task 2: Create account deletion service (AC: #2, #4, #5)
  - [x] 2.1 Create `backend/app/services/account_deletion_service.py` with `delete_all_user_data(session, user_id, cognito_sub, s3_keys)` function
  - [x] 2.2 Implement S3 bulk deletion: collect all `s3_key` values from user's `uploads` table, call `s3_client.delete_objects(Bucket=..., Delete={'Objects': [{'Key': k} for k in keys]})` in batches of 1000 (S3 API limit)
  - [x] 2.3 Implement DB cascade deletion: delete the `User` row — rely on `ON DELETE CASCADE` for all child tables (uploads, transactions, insights, processing_jobs, financial_profiles, financial_health_scores, flagged_import_rows, user_consents)
  - [x] 2.4 Call `CognitoService.delete_user(cognito_sub)` to remove from identity provider
  - [x] 2.5 Log audit entry via `logger.info` with only `user_id` and timestamp (no PII)

- [x] Task 3: Alembic migration — add ON DELETE CASCADE to all user_id FKs (AC: #2)
  - [x] 3.1 Create new Alembic migration that alters FK constraints on tables: `uploads`, `transactions`, `insights`, `processing_jobs`, `financial_profiles`, `financial_health_scores`, `flagged_import_rows` to add `ondelete="CASCADE"` (note: `user_consents` already has CASCADE per architecture doc)
  - [x] 3.2 For each table: `op.drop_constraint(...)` then `op.create_foreign_key(...)` with `ondelete="CASCADE"` — use `batch_alter_table` if targeting SQLite test DB

- [x] Task 4: Create DELETE API endpoint (AC: #1–#5)
  - [x] 4.1 Create `backend/app/api/v1/account.py` with `DELETE /users/me` endpoint
  - [x] 4.2 Use `get_current_user` dependency (need full User object for `cognito_sub`)
  - [x] 4.3 Orchestrate: query S3 keys from uploads → call account_deletion_service → return HTTP 204
  - [x] 4.4 Register router in `backend/app/api/v1/router.py`

- [x] Task 5: Backend tests (AC: #2, #4, #5)
  - [x] 5.1 Create `backend/tests/test_account_deletion_api.py`
  - [x] 5.2 Test successful deletion — user + all child data removed from DB, returns 204
  - [x] 5.3 Test tenant isolation — user B's data unaffected after user A deleted
  - [x] 5.4 Test unauthenticated request returns 401
  - [x] 5.5 Test S3 deletion is called with correct keys (mock boto3)
  - [x] 5.6 Test Cognito deletion is called (mock CognitoService)

- [x] Task 6: Install shadcn AlertDialog component (AC: #1)
  - [x] 6.1 Run `pnpm dlx shadcn@latest add alert-dialog` in frontend/ to add AlertDialog primitive
  - [x] 6.2 Verify `frontend/src/components/ui/alert-dialog.tsx` is created

- [x] Task 7: Create DataDeletion frontend component (AC: #1, #3)
  - [x] 7.1 Create `frontend/src/features/settings/components/DataDeletion.tsx` — danger zone card with "Delete All My Data" button
  - [x] 7.2 Implement AlertDialog confirmation: title warns permanent deletion, description lists what will be deleted, Cancel + destructive Confirm buttons
  - [x] 7.3 Create `frontend/src/features/settings/hooks/use-account-deletion.ts` — hook that calls `DELETE /api/v1/users/me` with session token, handles loading/error state
  - [x] 7.4 On successful deletion: show `toast.success()` message, then `signOut({ callbackUrl: '/${locale}/login' })` to redirect to landing page
  - [x] 7.5 On error: show `toast.error()` message, keep dialog closed, user can retry

- [x] Task 8: Integrate DataDeletion into SettingsPage (AC: #1)
  - [x] 8.1 Import and render `DataDeletion` in `SettingsPage.tsx` below `MyDataSection`
  - [x] 8.2 Add i18n keys under `settings.deleteData.*` namespace in `frontend/messages/en.json` and `frontend/messages/uk.json` (button label, dialog title, dialog description, cancel, confirm, success toast, error toast)

- [x] Task 9: Frontend tests (AC: #1, #3)
  - [x] 9.1 Create `frontend/src/features/settings/__tests__/DataDeletion.test.tsx`
  - [x] 9.2 Test: delete button renders, clicking opens dialog, cancel closes dialog, confirm calls API
  - [x] 9.3 Test: successful deletion calls signOut with redirect
  - [x] 9.4 Test: error state shows toast and does not sign out
  - [x] 9.5 Update `SettingsPage.test.tsx` — assert DataDeletion renders within settings page

- [x] Task 10: Full regression test (all ACs)
  - [x] 10.1 Run `cd backend && python -m pytest` — all tests pass
  - [x] 10.2 Run `cd frontend && pnpm test` — all tests pass

## Dev Notes

### Architecture & Patterns

- **Full-stack story**: new backend DELETE endpoint + new frontend danger-zone component + Alembic migration for CASCADE FKs.
- **Deletion order matters**: (1) Collect S3 keys from uploads, (2) Delete S3 objects, (3) Delete User row (cascades all child tables), (4) Delete Cognito user. If Cognito deletion fails after DB deletion, log a warning but don't fail — the user is already gone from the app, and orphaned Cognito entries can be cleaned up separately.
- **No application-level CASCADE needed**: Architecture specifies `ON DELETE CASCADE` on all `user_id` FKs. Deleting the `users` row automatically cascades to all child tables. The Alembic migration must add this to existing FKs that don't have it yet.
- **`document_embeddings` table is NOT user-scoped**: It stores RAG corpus embeddings with `doc_id` (string), not `user_id`. Do NOT touch this table during user deletion.
- **Backend router pattern**: Follow `data_summary.py` as reference. Use `APIRouter(prefix="/users/me", tags=["user-data"])`. Auth via `Annotated[User, Depends(get_current_user)]` from `deps.py` (need full User object to get `cognito_sub`).
- **HTTP 204**: Architecture specifies HTTP 204 for DELETE operations. No response body.
- **S3 batch delete**: `delete_objects()` supports up to 1000 keys per call. Users likely have <100 uploads, so single batch is fine, but handle batching for safety.

### Key Database Tables Affected by Cascade

| Table | FK Column | Current CASCADE? | Action |
|-------|-----------|-----------------|--------|
| `uploads` | `user_id` | No | Add CASCADE via migration |
| `transactions` | `user_id` | No | Add CASCADE via migration |
| `transactions` | `upload_id` | Check | May already cascade through uploads |
| `insights` | `user_id` | No | Add CASCADE via migration |
| `processing_jobs` | `user_id` | No | Add CASCADE via migration |
| `financial_profiles` | `user_id` | No | Add CASCADE via migration |
| `financial_health_scores` | `user_id` | No | Add CASCADE via migration |
| `flagged_import_rows` | `user_id` | No | Add CASCADE via migration |
| `user_consents` | `user_id` | Yes (per architecture) | Verify, no change needed |

### CognitoService Extension

- Add `delete_user()` method using `admin_delete_user` Cognito API call
- Uses `self._user_pool_id` and `Username=cognito_sub` (the sub UUID, not email)
- Handle `UserNotFoundException` gracefully (user may already be deleted from Cognito)
- Pattern: follow existing `global_sign_out()` method structure

### Frontend Patterns

- **No AlertDialog exists yet**: Must install via `pnpm dlx shadcn@latest add alert-dialog` — provides `AlertDialog`, `AlertDialogTrigger`, `AlertDialogContent`, `AlertDialogHeader`, `AlertDialogTitle`, `AlertDialogDescription`, `AlertDialogFooter`, `AlertDialogCancel`, `AlertDialogAction`
- **Logout after deletion**: Use `signOut({ callbackUrl: '/${locale}/login' })` from `next-auth/react` — same pattern as dashboard layout logout handler
- **Toast notifications**: Use `toast` from `sonner` (already used in dashboard layout)
- **Destructive button styling**: Use `variant="destructive"` on Button and AlertDialogAction
- **i18n**: Keys under `settings.deleteData.*` namespace. Both `en.json` and `uk.json` must be updated

### Audit Logging

- Per AC #5: log `user_id` + `timestamp` only — no email, no personal data
- Use Python `logger.info("User data deleted", extra={"user_id": str(user_id), "timestamp": ...})`
- This is a structured log entry, not a DB record — consistent with the project's current logging approach (structured logging with correlation IDs is Epic 6 scope)

### Previous Story Intelligence (5.4)

- **Data summary endpoint** (`data_summary.py`) queries all the same tables we need to delete from — use it as reference for which tables to target
- **MyDataSection** UI is where the delete button logically belongs (or adjacent to it)
- **Test patterns**: pytest with dependency overrides for auth; Vitest + @testing-library/react for frontend; `vi.mock` for next-intl, next-auth
- **Debug learnings**: SQLAlchemy `func.count()` returns Row tuples — use `scalar_one()`. SQLModel `select(Model)` returns ORM objects correctly.
- **i18n keys**: Hierarchical dot-separated, matching keys in both `en.json` and `uk.json`

### Git Intelligence

- Recent commits: "Story 5.4: View My Stored Data", "Story 5.2: Privacy Explanation & Consent During Onboarding", "Story 5.1: Data Encryption at Rest"
- Same epic, clean working tree, no conflicts expected
- Commit message pattern: "Story X.Y: Title"

### Testing Standards

- **Backend**: pytest + pytest-asyncio; test DB fixtures in `conftest.py`; dependency overrides for auth; mock boto3 S3 client and CognitoService. Reference: `backend/tests/test_data_summary_api.py`
- **Frontend**: Vitest + @testing-library/react; `vi.mock` for next-intl, next-auth, sonner; `global.fetch` mocked. Reference: `frontend/src/features/settings/__tests__/MyDataSection.test.tsx`
- **Run commands:**
  - `cd backend && python -m pytest tests/test_account_deletion_api.py -v`
  - `cd frontend && pnpm test -- DataDeletion`
  - `cd frontend && pnpm test -- SettingsPage`
  - `cd backend && python -m pytest` (full backend regression)
  - `cd frontend && pnpm test` (full frontend regression)

### Project Structure Notes

- Alignment with unified project structure: feature-based folders under `features/`, tests co-located in `__tests__/`, backend routers in `api/v1/`, services in `services/`
- New service file `account_deletion_service.py` follows existing pattern of `upload_service.py`, `cognito_service.py`
- No detected conflicts or variances

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 5, Story 5.5]
- [Source: _bmad-output/planning-artifacts/architecture.md — Privacy & Deletion, Consent Management, API Architecture]
- [Source: backend/app/api/v1/data_summary.py — Query pattern for all user tables]
- [Source: backend/app/services/cognito_service.py — Cognito API patterns, admin_delete_user]
- [Source: backend/app/services/upload_service.py — S3 client, key pattern, boto3 usage]
- [Source: backend/app/api/deps.py — get_current_user, get_current_user_id dependencies]
- [Source: backend/app/models/user.py — User model structure]
- [Source: frontend/src/features/settings/components/MyDataSection.tsx — Data section UI]
- [Source: frontend/src/app/[locale]/(dashboard)/layout.tsx — signOut pattern, toast usage]
- [Source: _bmad-output/implementation-artifacts/5-4-view-my-stored-data.md — Previous story patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- SQLite FK enforcement required explicit child record deletion in account_deletion_service (CASCADE only exists via Alembic migration on PostgreSQL)
- shadcn AlertDialog install updated button.tsx (minor style tweak for aria-haspopup)

### Completion Notes List

- Task 1: Added `delete_user()` method to CognitoService — handles UserNotFoundException gracefully (returns success if already deleted)
- Task 2: Created `account_deletion_service.py` — explicit child table deletion (defensive, works regardless of CASCADE), S3 batch delete, Cognito cleanup, audit logging
- Task 3: Created Alembic migration `h4i5j6k7l8m9` — adds ON DELETE CASCADE to all user_id and upload_id FKs (except user_consents which already had it)
- Task 4: Created `DELETE /api/v1/users/me` endpoint returning HTTP 204, registered in router
- Task 5: 5 backend tests — successful deletion, tenant isolation, unauthenticated 401, S3 keys verification, Cognito call verification
- Task 6: Installed shadcn AlertDialog component
- Task 7: Created DataDeletion component with AlertDialog confirmation, destructive styling, toast notifications, signOut redirect
- Task 8: Integrated DataDeletion below MyDataSection in SettingsPage, added i18n keys in en.json and uk.json
- Task 9: 5 frontend tests — renders button, opens/closes dialog, successful deletion with signOut, error handling
- Task 10: Full regression — 352 backend tests passed, 317 frontend tests passed

### Change Log

- 2026-04-12: Story 5.5 implemented — full-stack account deletion with confirmation dialog, cascade deletion, audit logging
- 2026-04-12: Code review fixes — moved S3 deletion after DB commit (data safety), wrapped S3 call in asyncio.to_thread (non-blocking), expanded test coverage to verify all 8 child tables, fixed Cognito error code to COGNITO_DELETE_ERROR

### File List

**New files:**
- backend/app/services/account_deletion_service.py
- backend/app/api/v1/account.py
- backend/alembic/versions/h4i5j6k7l8m9_add_cascade_delete_user_fks.py
- backend/tests/test_account_deletion_api.py
- frontend/src/components/ui/alert-dialog.tsx
- frontend/src/features/settings/components/DataDeletion.tsx
- frontend/src/features/settings/hooks/use-account-deletion.ts
- frontend/src/features/settings/__tests__/DataDeletion.test.tsx

**Modified files:**
- backend/app/services/cognito_service.py (added delete_user method)
- backend/app/api/v1/router.py (registered account router)
- frontend/src/features/settings/components/SettingsPage.tsx (added DataDeletion import/render)
- frontend/src/features/settings/__tests__/SettingsPage.test.tsx (added DataDeletion mock + test)
- frontend/src/components/ui/button.tsx (shadcn update — minor style tweak)
- frontend/messages/en.json (added settings.deleteData i18n keys)
- frontend/messages/uk.json (added settings.deleteData i18n keys)
- _bmad-output/implementation-artifacts/sprint-status.yaml (status update)
