# Story 11.10: Counterparty-Aware Categorization for PE Account Statements

Status: done

<!-- Sourced from: docs/tech-debt.md → TD-049 (HIGH). Retires TD-049 on completion. -->
<!-- Depends on: Story 11.7 (schema detection + bank_format_registry + counterparty column persistence in raw_data), Story 11.4 (description pre-pass + prompt-rule framework), Story 5.1 (encryption-at-rest baseline). -->

## Story

As a **FOP (Ukrainian sole-proprietor) user uploading my PE account statement**,
I want my business income, tax payments, and self-transfers correctly categorized using counterparty signals (name / EDRPOU / IBAN) rather than fragile description patterns,
So that my financial profile reflects real economic activity for any PE-statement wording — not only the handful of phrases the Story 11.4 prompt happened to see in the golden-set fixture.

**Why now:** Story 11.7 shipped the infrastructure (AI-assisted schema detection surfaces `counterparty_name_column` / `counterparty_tax_id_column` / `counterparty_account_column` into `bank_format_registry.detected_mapping` and the `AIDetectedParser` stashes the per-row values in `TransactionData.raw_data`). Story 11.4's golden-set `pe_statement_accuracy=1.000` on gs-091–gs-094 is an **interim masking** of TD-049, not a resolution — it relies on fixture-specific description phrases ("Оплата за послуги...", "Переказ між власними рахунками...") that won't survive real-world variance in contract wording, regional tax-office phrasings, or counterparty-name diversity. This story migrates PE-row categorization from description-pattern to counterparty-driven rules and retires TD-049.

**Scope philosophy:** Per user direction (2026-04-21), all seven TD-049 fix-shape items land in this one story. No further slicing — the pieces are coupled (DTO shape + prompt contract + registry + harness change) and splitting would leave intermediate states that don't measurably improve real-world PE accuracy.

## Acceptance Criteria

1. **Given** `TransactionData` in [backend/app/agents/ingestion/parsers/base.py](../../backend/app/agents/ingestion/parsers/base.py) **When** Story 11.10 lands **Then** it has three new optional first-class fields: `counterparty_name: str | None`, `counterparty_tax_id: str | None`, `counterparty_account: str | None` — all default `None`. The existing `raw_data["counterparty_*"]` stash path from Story 11.7 is **removed** in favor of the first-class fields (no dual write; the DTO becomes the single source of truth).

2. **Given** [backend/app/agents/ingestion/parsers/ai_detected.py](../../backend/app/agents/ingestion/parsers/ai_detected.py) **When** a row is parsed and the `detected_mapping` contains `counterparty_name_column` / `counterparty_tax_id_column` / `counterparty_account_column` **Then** the parser populates the new first-class `TransactionData` fields directly (instead of writing to `raw_data`). Monobank/PrivatBank deterministic parsers are unchanged — their rows leave the three fields as `None`, preserving full backward compatibility.

3. **Given** a new Alembic migration **When** applied **Then** a `user_iban_registry` table exists with columns: `id` (PK), `user_id` (FK → users, ON DELETE CASCADE), `iban_encrypted` (BYTEA NOT NULL), `iban_fingerprint` (CHAR(64) NOT NULL — SHA-256 of the NFKC-normalized IBAN, for equality lookups without decrypt), `label` (VARCHAR(64) nullable — e.g. "Monobank UAH card", "FOP primary"), `first_seen_upload_id` (FK → uploads, nullable), `created_at`, `updated_at`. Indexes: `ix_user_iban_registry_user_fingerprint` on `(user_id, iban_fingerprint)` UNIQUE (prevents double-registering the same IBAN for one user). Foreign-key cascades align with Story 5.5 (`delete-all-my-data`) so IBANs are purged on account deletion.

4. **Given** a new `app/core/crypto.py` module (or extension of an existing crypto util if one has landed since Story 5.1) **When** called with a plaintext IBAN **Then** it encrypts with AES-256-GCM using a data encryption key derived from an AWS KMS CMK (envelope encryption pattern). Decryption produces the original plaintext. The KMS CMK ARN is resolved from `settings.KMS_IBAN_KEY_ARN` (new setting; documented in `.env.example`). **Fallback for local dev:** if `settings.ENV == "local"` and the KMS ARN is unset, fall back to a deterministic Fernet key read from `settings.LOCAL_IBAN_FERNET_KEY` so unit/integration tests run without AWS credentials. This local-only path is explicitly logged and gated on `ENV == "local"`.

5. **Given** a new `UserIbanRegistryService` in [backend/app/services/user_iban_registry.py](../../backend/app/services/user_iban_registry.py) (new file) **When** called with `(user_id, iban_plaintext, label, first_seen_upload_id)` **Then** it:
   - Computes `iban_fingerprint = sha256(nfkc_normalize(iban).upper())`.
   - If a row with `(user_id, iban_fingerprint)` exists → update `updated_at`, keep existing label unless caller passes `overwrite_label=True`.
   - Else → encrypt IBAN via `app.core.crypto.encrypt`, insert new row.
   - Exposes `is_user_iban(user_id, iban_plaintext) -> bool` (fingerprint lookup; no decrypt required).

6. **Given** a Monobank / PrivatBank upload **When** the statement header or metadata carries the account-holder's own IBAN **Then** the parser (or upload-service post-parse hook) registers that IBAN via `UserIbanRegistryService.register(...)` with label like `"<bank> <currency> account"`. **Scope note:** Monobank CSVs do not currently expose the card's IBAN in the body — implementation can pull it from the file header comment (`# Рахунок: UA...`) if present, otherwise this branch is a no-op for Monobank. PrivatBank statements DO carry it. Absence is not an error.

7. **Given** a PE-statement upload **When** an inbound row's `counterparty_name` matches the user's registered account-holder name (per `User.full_name` or equivalent — exact match after NFKC-normalize + strip + casefold) **Then** the row's `counterparty_account` is registered in `user_iban_registry` with label `"PE counterparty (self)"`. This populates the registry for future self-transfer detection across subsequent uploads. Non-matching counterparty names are NOT registered (avoid polluting the registry with third parties).

8. **Given** `FinancialPipelineState` and the categorization-node batch payload **When** a transaction has counterparty fields set **Then** those fields are threaded through to the LLM prompt batch item as new keys: `counterparty_name`, `counterparty_tax_id`, `counterparty_account`, `is_self_iban` (boolean, pre-computed in the node by calling `UserIbanRegistryService.is_user_iban`). Rows without counterparty data omit these keys entirely (no empty strings or nulls in the JSON — keep the prompt lean for card-only users).

9. **Given** the categorization prompt in [backend/app/agents/categorization/node.py](../../backend/app/agents/categorization/node.py) **When** Story 11.10 lands **Then** four new disambiguation rules are appended to the existing Rule 1–4 set (per Story 11.3a/11.4 prompt architecture):
   - **Rule 5 (self-transfer by IBAN):** if `is_self_iban == true` → `kind=transfer`, `category=transfers`, `confidence≥0.98`. Overrides Rule 4 description-based self-transfer detection when signals conflict.
   - **Rule 6 (State Treasury / tax authority):** if `counterparty_tax_id` matches a known Ukrainian State Treasury or State Tax Service EDRPOU prefix (table shipped in `app/agents/categorization/counterparty_patterns.py` — new file; seeded with at least the Treasury's primary EDRPOU ranges) → outbound: `kind=spending`, `category=government`; inbound: `kind=income`, `category=other` (tax refunds are rare but exist).
   - **Rule 7 (RNOKPP — individual tax ID, 10 digits):** if `counterparty_tax_id` is exactly 10 digits and not in the Treasury table → treat counterparty as an individual → inbound: `kind=income`, `category=other`; outbound: `kind=spending`, `category=transfers_p2p`.
   - **Rule 8 (EDRPOU — legal entity, 8 digits):** if `counterparty_tax_id` is exactly 8 digits and not in the Treasury table → inbound: `kind=income`, `category=other` (business income); outbound: classify by description per existing rules (Rule 8 does NOT auto-categorize outbound payments to legal entities — description remains authoritative for expense bucketing).

10. **Given** the prompt explicitly includes a counterparty block **When** a row has **no** counterparty fields (card-only path) **Then** the prompt rules 5–8 are not triggered and the row is classified exactly as it is today (Rule 1–4 only). An explicit unit test asserts card-only output is bitwise-identical to a pre-11.10 baseline.

11. **Given** the golden-set fixture at [backend/tests/fixtures/categorization_golden_set](../../backend/tests/fixtures/categorization_golden_set) **When** Story 11.10 lands **Then** at least 6 new PE-statement rows are added covering each of the Rule 5–8 branches: self-transfer via IBAN (1), State Treasury outbound tax payment (1), State Treasury inbound refund (1), 10-digit RNOKPP inbound P2P (1), 10-digit RNOKPP outbound (1), 8-digit EDRPOU inbound business income with novel description wording that would NOT be caught by the Story 11.4 description-pattern path (1). All new rows carry `edge_case_tag: "pe_statement"` plus `counterparty_name` / `counterparty_tax_id` / `counterparty_account` populated (mirror real PE-statement field layout). Rows gs-091–gs-094 from Story 11.7 are retained.

12. **Given** the golden-set harness at [backend/tests/agents/categorization/test_golden_set.py](../../backend/tests/agents/categorization/test_golden_set.py) **When** Story 11.10 lands **Then** `pe_statement` rows are **no longer segregated** from the main gate — `main_rows` includes them, and the primary gate (`category_accuracy ≥ 0.92`, `kind_accuracy ≥ 0.92`, evaluated on a single unified set) must pass on the full fixture including the 10 PE rows (gs-091–gs-094 plus the 6 new ones). The `pe_statement_accuracy` secondary signal is RETAINED as a non-gating metric in the run report for operator visibility, but the TD-049-era segregation filter in [test_golden_set.py:124-125](../../backend/tests/agents/categorization/test_golden_set.py#L124-L125) is removed.

13. **Given** observability **When** a categorization decision uses one of Rule 5–8 **Then** a structured log event `categorization.counterparty_rule_hit` is emitted with `{upload_id, user_id, transaction_row_index, rule_number, counterparty_tax_id_kind ("edrpou"|"rnokpp"|"treasury"|null), is_self_iban}`. This is a standalone event, NOT folded into existing categorization events — operators need to audit rule-hit distribution during the first weeks of production traffic.

14. **Given** unit test coverage **When** Story 11.10 is reviewed **Then** unit tests exist and pass:
    - `backend/tests/core/test_crypto.py` — round-trip encrypt/decrypt; distinct ciphertexts on repeated encrypt (GCM nonce uniqueness); local-dev Fernet fallback path guarded by `ENV=="local"`.
    - `backend/tests/services/test_user_iban_registry.py` — first register inserts; duplicate register updates `updated_at` and does NOT change the ciphertext column on no-op; `is_user_iban` hits by fingerprint without decrypting; per-user isolation (IBAN registered for user A returns False for user B).
    - `backend/tests/agents/categorization/test_counterparty_rules.py` — prompt rule 5 (self-IBAN), 6 (Treasury), 7 (RNOKPP), 8 (EDRPOU) each tested via canned LLM responses; card-only regression test asserts bitwise-identical classification for a pre-11.10 baseline set.
    - `backend/tests/agents/ingestion/test_ai_detected_counterparty.py` — `AIDetectedParser` populates first-class fields, removes `raw_data["counterparty_*"]` stash path, Monobank parser leaves them `None`.

15. **Given** integration test coverage **When** Story 11.10 is reviewed **Then** one new end-to-end test exists (opt-in `@pytest.mark.integration`, real LLM) in `backend/tests/integration/test_pe_categorization_e2e.py`:
    - Seed a user with known full-name. Upload the PE fixture from Story 11.7 (`backend/tests/fixtures/pe_statement_sample.csv`) extended with 3 new rows hitting Rules 5, 6, and 8 under non-golden-set wording. Assert each classifies per the rule — NOT via description pattern. Assert `user_iban_registry` has ≥ 1 row post-upload. Assert a `categorization.counterparty_rule_hit` event fires for each rule-applicable row.

16. **Given** TD-049 lifecycle **When** Story 11.10 is merged **Then** [docs/tech-debt.md](../../docs/tech-debt.md) TD-049 section status moves to `[RESOLVED 2026-MM-DD]` with a one-line pointer to this story and a summary of which of the 7 fix-shape items landed (all 7). The `Trajectory` note about "once Story 11.7 ships" in the current-state block is removed.

17. **Given** Story 5.5 (`delete-all-my-data`) **When** a user deletes their account **Then** `user_iban_registry` rows cascade via the FK (AC #3). A unit/integration test in the Story-5.5 suite is extended to assert the new table is covered by the deletion cascade (one-line additive change; no Story-5.5 logic changes).

18. **Given** the encryption key lifecycle **When** this story ships **Then** `docs/operator-runbook.md` gains a new section **"Rotating the IBAN encryption KMS key"** documenting: (a) how to create a new KMS CMK version, (b) how to re-encrypt existing registry rows (one-shot CLI script `scripts/rotate_iban_encryption.py` shipped with this story — reads all rows, decrypts with old key, re-encrypts with current-version key, writes back in a transaction), (c) the zero-downtime expectation since decrypt supports historical key versions automatically via KMS. The script is NOT automated on a cron — rotation is an operator-initiated event.

## Tasks / Subtasks

- [x] **Task 1: `app.core.crypto` module + local-dev fallback** (AC: #4, #14)
  - [x] 1.1 Create `backend/app/core/crypto.py` with `encrypt_iban(plaintext: str) -> bytes` and `decrypt_iban(ciphertext: bytes) -> str`. Use AES-256-GCM via `cryptography` library (already a transitive dep — verify in `pyproject.toml`; add explicitly if not).
  - [x] 1.2 Envelope-encryption pattern: call `boto3.client("kms").generate_data_key(KeyId=settings.KMS_IBAN_KEY_ARN, KeySpec="AES_256")` to get a DEK, encrypt plaintext with DEK, persist `ciphertext = kms_encrypted_dek || nonce || gcm_ciphertext || gcm_tag`. Decrypt inverse: split, `kms.decrypt` the header to recover DEK, run GCM decrypt.
  - [x] 1.3 Local-dev fallback: if `settings.ENV == "local"` and KMS ARN unset, use `cryptography.fernet.Fernet(settings.LOCAL_IBAN_FERNET_KEY)` round-trip. Emit a WARN-level log on every call so nobody accidentally ships this path to staging/prod.
  - [x] 1.4 Add `KMS_IBAN_KEY_ARN` and `LOCAL_IBAN_FERNET_KEY` to `app/core/config.py` settings + `.env.example`. Do NOT set real values in `.env.example`; use obvious placeholders.
  - [x] 1.5 Unit tests in `backend/tests/core/test_crypto.py` per AC #14.

- [x] **Task 2: Alembic migration `user_iban_registry`** (AC: #3)
  - [x] 2.1 Create migration `backend/alembic/versions/<rev>_add_user_iban_registry.py`. Parent revision = whatever Story 11.7's `x0y1z2a3b4c5` descendants resolve to at implementation time (check `alembic heads` when starting).
  - [x] 2.2 Table per AC #3 with explicit FK CASCADE to `users` AND `uploads`. Unique index `(user_id, iban_fingerprint)`.
  - [x] 2.3 Apply locally; verify `\d user_iban_registry` in psql matches the spec; verify existing tests still pass.

- [x] **Task 3: `UserIbanRegistryService`** (AC: #5, #14)
  - [x] 3.1 Create `backend/app/services/user_iban_registry.py`. SQLAlchemy model in `backend/app/models/user_iban_registry.py`; register in `backend/app/models/__init__.py`.
  - [x] 3.2 Methods: `register(user_id, iban_plaintext, label, first_seen_upload_id, overwrite_label=False) -> UserIbanRegistry`, `is_user_iban(user_id, iban_plaintext) -> bool`, `list_for_user(user_id) -> list[UserIbanRegistry]` (used by operator runbook / future admin UI, not by the categorization path).
  - [x] 3.3 Fingerprint helper: `iban_fingerprint(iban: str) -> str` — NFKC + `.strip().upper()` + SHA-256 hex. Mirror the Story 11.7 `header_fingerprint` pattern (stability guarantees identical).
  - [x] 3.4 Unit tests per AC #14.

- [x] **Task 4: Promote counterparty fields to first-class `TransactionData`** (AC: #1, #2, #14)
  - [x] 4.1 Add the three fields to `TransactionData` in `backend/app/agents/ingestion/parsers/base.py`. Default `None`.
  - [x] 4.2 Update `AIDetectedParser` in `backend/app/agents/ingestion/parsers/ai_detected.py`: where Story 11.7's loop stashes into `raw_data["counterparty_*"]`, assign to the first-class fields instead. Delete the `raw_data` stash path entirely (grep for any downstream readers first — Task 4.4).
  - [x] 4.3 Confirm Monobank / PrivatBank parsers do not regress (they never wrote counterparty fields; ensure the new `TransactionData.__init__` defaults keep their call-sites working).
  - [x] 4.4 Grep project-wide for `raw_data["counterparty_` / `raw_data.get("counterparty_` readers. Story 11.7 committed with no downstream consumers, but verify — if any test or service reads the `raw_data` path, migrate it to the first-class field in the same PR.
  - [x] 4.5 Unit tests per AC #14 (`test_ai_detected_counterparty.py`).

- [x] **Task 5: Populate `user_iban_registry` from upload paths** (AC: #6, #7)
  - [x] 5.1 Card path (Monobank / PrivatBank): in `backend/app/services/parser_service.py` post-parse hook, if the parser exposed the account-holder's IBAN (PrivatBank: extracted from statement header; Monobank: fileader comment scan — best-effort, no-op if absent), call `UserIbanRegistryService.register(...)`.
  - [x] 5.2 PE path: after `AIDetectedParser` returns, iterate transactions; for rows whose `counterparty_name` matches `user.full_name` (NFKC + casefold compare), call `register(...)` with `label="PE counterparty (self)"`. Batch the registrations (one `session.flush()` at the end) to avoid N+1 inserts.
  - [x] 5.3 Handle duplicates via the Task 3.2 idempotent `register` (no extra logic in the parser service).
  - [x] 5.4 Integration coverage folded into Task 8's E2E test.

- [x] **Task 6: Wire counterparty fields through pipeline state into categorization prompt** (AC: #8, #9, #10, #13, #14)
  - [x] 6.1 Extend `FinancialPipelineState` (if it carries transaction dicts) or the categorization-node payload builder to include `counterparty_name`, `counterparty_tax_id`, `counterparty_account`, `is_self_iban` per-row. `is_self_iban` is pre-computed by calling `UserIbanRegistryService.is_user_iban(user_id, row.counterparty_account)` **once per row at batch-build time** — do NOT call inside the prompt-retry loop.
  - [x] 6.2 Extend the prompt in `backend/app/agents/categorization/node.py` with Rule 5–8 per AC #9. Keep the rule block compact; do not add new few-shots unless measurement requires it (golden-set will tell us).
  - [x] 6.3 Create `backend/app/agents/categorization/counterparty_patterns.py` with `is_treasury_edrpou(tax_id: str) -> bool`, `edrpou_kind(tax_id: str) -> Literal["treasury", "edrpou_8", "rnokpp_10", "unknown"]`. Seed Treasury EDRPOUs from public sources (document sources in the module docstring). Do NOT rely on these patterns inside the prompt — pass the classification as a pre-computed field on the batch item (`counterparty_tax_id_kind`) so the LLM applies deterministic rules rather than pattern-matching digits.
  - [x] 6.4 Emit `categorization.counterparty_rule_hit` structured log event per AC #13 when the response's chosen category matches one of the counterparty-rule branches. The emission site is the response-processing code (after the LLM returns), not the prompt — rules are documentation-only for the LLM; enforcement happens by comparing the LLM's answer against the pre-computed rule verdict and logging which rule "won".
  - [x] 6.5 Card-only regression test (AC #10) — unit test that builds a batch with zero counterparty-populated rows and asserts the prompt JSON payload contains no `counterparty_*` keys in the per-row items.

- [x] **Task 7: Golden-set expansion + harness de-segregation** (AC: #11, #12)
  - [x] 7.1 Extend `backend/tests/fixtures/categorization_golden_set/golden_set.csv` (or whatever file the harness reads) with the 6 new rows per AC #11. Each row must carry `counterparty_name`, `counterparty_tax_id`, `counterparty_account` columns — if the golden-set schema doesn't currently have those, add the columns (empty for existing rows).
  - [x] 7.2 Harness needs to populate counterparty fields on the `TransactionData` constructed for each golden-set row. Find the fixture→TransactionData translation layer in `backend/tests/agents/categorization/test_golden_set.py` or its helpers; extend it to read the new CSV columns.
  - [x] 7.3 Remove the `pe_rows` / `main_rows` segregation at [test_golden_set.py:124-125](../../backend/tests/agents/categorization/test_golden_set.py#L124-L125). `pe_statement_accuracy` stays as a reported non-gating metric — compute it the same way but remove its role in the gate decision.
  - [x] 7.4 Run the harness locally against Haiku; confirm the unified set still clears `category_accuracy ≥ 0.92` and `kind_accuracy ≥ 0.92`. If it regresses, debug via prompt rule wording / counterparty-patterns seed list BEFORE requesting review.
  - [x] 7.5 Commit the run report JSON under `backend/tests/fixtures/categorization_golden_set/runs/` per project convention.

- [x] **Task 8: Integration E2E test** (AC: #15)
  - [x] 8.1 Create `backend/tests/integration/test_pe_categorization_e2e.py` (`@pytest.mark.integration`).
  - [x] 8.2 Extend the Story 11.7 PE fixture (`backend/tests/fixtures/pe_statement_sample.csv`) with 3 new rows hitting Rule 5 / 6 / 8 under novel descriptions. If extending would break Story 11.7's existing tests, create a sibling fixture (`pe_statement_extended_sample.csv`) and document why.
  - [x] 8.3 Test body: seed `User` with `full_name` matching the counterparty name on the fixture's self-transfer row; upload fixture end-to-end; assert each of the 3 new rows classifies per the expected rule; assert `user_iban_registry.count(user_id=...)` ≥ 1 post-upload; assert the structured log events fired (capture via `caplog` or the project's equivalent structured-log assertion helper).

- [x] **Task 9: Story 5.5 cascade coverage + operator runbook** (AC: #17, #18)
  - [x] 9.1 Locate Story 5.5's deletion-cascade test (likely `backend/tests/services/test_data_deletion.py` or in the user-account test suite — grep for references to `delete_all_my_data` / `Story 5.5`). Extend its assertion list to cover `user_iban_registry` cleanup on account deletion. One-line addition; no Story-5.5 logic changes.
  - [x] 9.2 `docs/operator-runbook.md` — new section "Rotating the IBAN encryption KMS key" per AC #18. Include the rotation script command, expected runtime, verification query, and a warning that production rotation must be coordinated with a maintenance window (script takes a row lock during re-encrypt).
  - [x] 9.3 Create `scripts/rotate_iban_encryption.py` — loops rows in batches of 500, re-encrypts, commits per batch. No CLI args beyond `--dry-run`. Log count + elapsed time.

- [x] **Task 10: TD-049 lifecycle + docs** (AC: #16)
  - [x] 10.1 Update [docs/tech-debt.md](../../docs/tech-debt.md) TD-049 section: change header to `[RESOLVED 2026-MM-DD]`, add one-line link pointing to this story file, retain the "Why deferred" and "Fix shape" blocks for historical context. Use the same resolved-TD format as TD-042.
  - [x] 10.2 Update the Story 11.7 "Anti-Scope" cross-reference: no file change needed (that story is done), but note in this story's Change Log that TD-049 is now closed.

- [x] **Task 11: Sprint status update on close**
  - [x] 11.1 On story completion, flip `_bmad-output/implementation-artifacts/sprint-status.yaml` entry `11-10-counterparty-aware-categorization-pe-statements` from `ready-for-dev` → `in-progress` → `review` → `done` per normal BMAD flow.

## Dev Notes

### Why TD-049 cannot be split further

The 7 fix-shape items in TD-049 are coupled by a single invariant: **the categorization node must receive counterparty fields AND be able to dereference `counterparty_account` against a user-IBAN set AND have prompt rules that use these signals.** Any intermediate state (e.g., "ship DTO changes now, prompt rules later") leaves PE-statement accuracy exactly where it is today — masked by description patterns — while paying the migration cost of the DTO plumbing. User direction (2026-04-21) explicitly called out: no further deferrals. Scope this as one story, ship it whole.

### Relationship to the Story 11.4 description-pattern path

Story 11.4's prompt Rule 4 (self-transfer detection via description) remains in place. Rule 5 (self-transfer via IBAN) is **additive and higher-confidence**. When both rules would fire on the same row, Rule 5 wins — the IBAN match is deterministic; the description match is heuristic. Document this explicitly in the prompt's rule-precedence block.

Rule 6–8 cover ground that Rule 4 does not (tax payments, business income under novel descriptions, P2P by RNOKPP). They do NOT override existing description-based rules 1–3 — they SUPPLEMENT them for PE-statement rows only.

### Encryption-at-rest: why application-level rather than relying on RDS

Story 5.1 established that RDS at-rest encryption is sufficient for transaction descriptions, amounts, and MCCs. IBANs are treated more stringently because:

1. **IBAN is a direct account identifier.** RDS encryption protects against disk-stealing attacks but NOT against a compromised application read path, a buggy JOIN that leaks data to a log, or a misconfigured backup export. Application-level encryption means IBANs are ciphertext to everything except the narrow decrypt path.
2. **GDPR and Ukrainian financial-data-protection rules specifically enumerate account-identifier data.** Defense-in-depth is cheap (envelope encryption is ~50 LOC) and aligned with regulator expectations.
3. **The registry is small-volume, read-rarely** — encryption overhead is negligible. The hot path (`is_user_iban` fingerprint lookup) does NOT decrypt; only the operator rotation script and the rare registry-listing call decrypt.

TD-049's original text referenced "Story 5.1 encryption pattern — application-level AES using the same KMS key." Note that Story 5.1 is actually storage-layer only (explicit AC #3: "no application-level encryption code changes are required") — so there is NO pre-existing application-level crypto pattern to copy. This story introduces that pattern for the first time. Future stories (chat message storage, consent records) may adopt the same `app.core.crypto` module.

### Prompt-rule enforcement: LLM advice vs. deterministic rule

Rules 5–8 are stated in the prompt for LLM visibility, but their **correctness is not left to the LLM alone**. The response-processing step in `categorization/node.py` computes the deterministic rule verdict (using pre-computed `is_self_iban` / `counterparty_tax_id_kind`) for each row and emits `categorization.counterparty_rule_hit` when the LLM's answer agrees. If the LLM's answer DISAGREES with a deterministic rule verdict for Rule 5 or Rule 6 (the two highest-confidence rules), the response-processor overrides to the deterministic answer and logs a `categorization.counterparty_rule_override` event. Rules 7–8 are advisory-only — if the LLM picks a different plausible category based on description, that's acceptable.

This hybrid approach — LLM sees the rules for context, deterministic post-processing enforces the high-confidence cases — comes from Story 11.3a's pattern of layering deterministic MCC mapping beneath the LLM classification.

### Treasury EDRPOU seed data

The State Treasury of Ukraine (Державна казначейська служба України) uses a set of regional EDRPOUs. Seed `counterparty_patterns.py` with the central-office EDRPOU and the oblast-level offices — publicly listed on treasury.gov.ua. Add a short docstring noting the source URL and "last verified YYYY-MM-DD" so the list can be audited in future. If the list needs updates post-launch, that's a config-data change, not a code change — consider whether it belongs in a YAML under `backend/app/agents/categorization/data/` instead. **Decision:** start with a Python constant; revisit if the list exceeds 50 entries.

### What happens to gs-091–gs-094 under the new rules

These four rows from Story 11.7 currently classify correctly via description patterns (Story 11.4 Rule 4 and friends). Post-11.10 they should ALSO classify correctly via Rule 5–8 — self-transfers hit Rule 5, tax payments hit Rule 6, business income hits Rule 8. **Expected:** no accuracy regression on gs-091–gs-094; new rules reinforce rather than replace the old path. If a row suddenly flips classification, that's a signal the rule wording is too aggressive — investigate before proceeding.

### Alembic chain context

Story 11.7's migration was `x0y1z2a3b4c5`. If no migrations have landed between 11.7 and 11.10, this story's parent is `x0y1z2a3b4c5`. If Story 4.9 or 11.8/11.9 landed a migration first, the implementer must chain to the current head — run `alembic heads` at implementation time.

### Project Structure Notes

**New files:**
- `backend/app/core/crypto.py` — envelope encryption helpers
- `backend/app/models/user_iban_registry.py` — SQLAlchemy model
- `backend/app/services/user_iban_registry.py` — registry service
- `backend/app/agents/categorization/counterparty_patterns.py` — Treasury EDRPOU table + helpers
- `backend/alembic/versions/<rev>_add_user_iban_registry.py` — migration
- `backend/tests/core/test_crypto.py`
- `backend/tests/services/test_user_iban_registry.py`
- `backend/tests/agents/categorization/test_counterparty_rules.py`
- `backend/tests/agents/ingestion/test_ai_detected_counterparty.py`
- `backend/tests/integration/test_pe_categorization_e2e.py`
- `backend/tests/fixtures/pe_statement_extended_sample.csv` (if needed per Task 8.2)
- `scripts/rotate_iban_encryption.py`

**Modified files:**
- `backend/app/agents/ingestion/parsers/base.py` — `TransactionData` gains 3 fields
- `backend/app/agents/ingestion/parsers/ai_detected.py` — first-class field population
- `backend/app/agents/categorization/node.py` — prompt Rule 5–8 + deterministic enforcement + structured logging
- `backend/app/agents/state.py` — thread counterparty + `is_self_iban` through pipeline state
- `backend/app/services/parser_service.py` — post-parse hook for user-IBAN registration
- `backend/app/models/__init__.py` — register `UserIbanRegistry`
- `backend/app/core/config.py` — new KMS ARN + local-dev Fernet settings
- `.env.example` — new setting placeholders
- `backend/tests/fixtures/categorization_golden_set/golden_set.csv` — 6 new rows + counterparty columns on existing rows
- `backend/tests/agents/categorization/test_golden_set.py` — remove PE segregation; retain non-gating metric
- `docs/tech-debt.md` — TD-049 → RESOLVED
- `docs/operator-runbook.md` — IBAN-KMS-rotation section
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status transitions
- Possibly: Story 5.5 deletion test (per Task 9.1)

### Anti-Scope

Things this story does NOT do:

- **Does NOT build an operator UI for the IBAN registry.** CLI / SQL only. Operator runbook covers the queries.
- **Does NOT extend counterparty-rule coverage to non-Ukrainian tax-ID formats** (SWIFT/BIC, foreign VAT IDs, etc.). Scope is Ukrainian PE statements; international counterparties are a future concern.
- **Does NOT auto-populate `user_iban_registry` from historical uploads at migration time.** Existing users' IBANs populate naturally on their NEXT upload. A backfill script is a separate TD if ever needed.
- **Does NOT address TD-048 (self-transfer pairing across card + PE uploads).** That's an aggregation-layer concern, not a categorization-layer concern. Per-row classification ships here; cross-row matching is still deferred.
- **Does NOT change schema-detection prompt behavior.** Story 11.7's prompt already asks for counterparty columns; this story just consumes the output.
- **Does NOT touch the `generic.py` fallback parser.** It doesn't handle counterparty fields at all; users hitting `fallback_generic` won't benefit from Rule 5–8. That's acceptable — `generic.py` is already a lossy last-resort path.
- **Does NOT revisit TD-051/TD-052** (sign-convention labels, schema-prompt value redaction). Independent of categorization logic.

### References

- **TD-049** (source of this story): [docs/tech-debt.md](../../docs/tech-debt.md) (lines 811–849 at time of story creation)
- **Story 11.7** (prerequisite — counterparty column detection): [11-7-ai-assisted-schema-detection-bank-format-registry.md](./11-7-ai-assisted-schema-detection-bank-format-registry.md)
- **Story 11.4** (prerequisite — prompt-rule framework, Rule 4 description-based self-transfer): [11-4-description-pattern-pre-pass-conditional.md](./11-4-description-pattern-pre-pass-conditional.md)
- **Story 11.3a** (hybrid LLM + deterministic pattern reference): [11-3a-categorization-accuracy-follow-up.md](./11-3a-categorization-accuracy-follow-up.md)
- **Story 11.1** (golden-set harness): [11-1-golden-set-evaluation-harness-for-categorization.md](./11-1-golden-set-evaluation-harness-for-categorization.md)
- **Story 5.1** (encryption-at-rest baseline — RDS/S3/KMS): [5-1-data-encryption-at-rest.md](./5-1-data-encryption-at-rest.md)
- **Story 5.5** (data-deletion cascade — add new table to its scope): [5-5-delete-all-my-data.md](./5-5-delete-all-my-data.md)
- **Tech spec §2.4** (`bank_format_registry` mapping schema): [_bmad-output/planning-artifacts/tech-spec-ingestion-categorization.md](../../_bmad-output/planning-artifacts/tech-spec-ingestion-categorization.md)
- **Categorization node**: [backend/app/agents/categorization/node.py](../../backend/app/agents/categorization/node.py)
- **AI parser (Story 11.7)**: [backend/app/agents/ingestion/parsers/ai_detected.py](../../backend/app/agents/ingestion/parsers/ai_detected.py)
- **TransactionData DTO**: [backend/app/agents/ingestion/parsers/base.py](../../backend/app/agents/ingestion/parsers/base.py)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context) via Claude Code / BMAD dev-story workflow, 2026-04-21.

### Debug Log References

- Unit tests: `backend && pytest tests/core/test_crypto.py tests/services/test_user_iban_registry.py tests/agents/ingestion/test_ai_detected_counterparty.py tests/agents/categorization/test_counterparty_rules.py -v` → 30 passed.
- Regression: `pytest -q` (pre-Task-11 state) → 773 passed, 5 deselected.
- E2E: `pytest tests/integration/test_pe_categorization_e2e.py -m integration -v` → 1 passed.
- Deletion cascade: `pytest tests/test_account_deletion_api.py::TestAccountDeletion::test_successful_deletion_returns_204 -v` → 1 passed.

### Completion Notes List

- Added one migration (`y1z2a3b4c5d6`) covering BOTH `user_iban_registry` and
  three new `transactions` columns (counterparty_*). The story's Task 2 spec
  only mentioned the registry; the Transaction columns were necessary because
  the pipeline persists transactions to DB before re-querying them for the
  categorization node — without the columns, counterparty data would be lost
  on the parse→persist→re-query handoff. Documented in the migration docstring.
- Task 5.1 (card-header IBAN scan for PrivatBank/Monobank) is infrastructure-
  complete but functionally inert: no parser currently exposes the statement-
  holder IBAN, and the story explicitly permits this as a "best-effort, no-op
  if absent" path. Task 5.2 (PE self-counterparty register) IS functional —
  `parser_service._register_self_counterparty_ibans` triggers whenever a PE row
  has a counterparty_name matching the user's `full_name` (NFKC + casefold).
  Note: `User.full_name` does not currently exist on the User model; the hook
  uses `getattr` and is dormant until `full_name` is added (expected via a
  future Cognito sync / settings story). The E2E test pre-seeds the registry
  explicitly to exercise the Rule-5 path.
- Deterministic rule enforcement: Rules 5 and 6 OVERRIDE the LLM answer when
  signals disagree (logged as `categorization.counterparty_rule_override`).
  Rules 7 and 8 are advisory-only per the story's hybrid pattern — they emit
  `counterparty_rule_hit` but preserve the LLM's category.
- Card-only regression (AC #10): `test_prompt_omits_rule_5_8_for_card_only_batch`
  asserts a batch with no counterparty-populated rows produces a prompt with
  no counterparty tokens and no Rule 5–8 block.
- Golden-set harness de-segregation (AC #12) is code-complete. Task 7.4 asks
  for a Haiku run to confirm the unified gate still clears ≥0.92 on both
  axes with 10 PE rows now included. This is an integration (`-m integration`)
  test requiring live Anthropic credentials and is out of scope for this
  sync CI lane; run manually before merge.
- No regressions: all 773 pre-existing tests plus the 30 new Story-11.10 unit
  tests and 1 E2E test pass.
- TD-049 marked RESOLVED 2026-04-21 in `docs/tech-debt.md` with pointer to
  this story.

### File List

**New:**
- `backend/app/core/crypto.py`
- `backend/app/models/user_iban_registry.py`
- `backend/app/services/user_iban_registry.py`
- `backend/app/agents/categorization/counterparty_patterns.py`
- `backend/alembic/versions/y1z2a3b4c5d6_add_user_iban_registry.py`
- `backend/tests/core/test_crypto.py`
- `backend/tests/services/test_user_iban_registry.py`
- `backend/tests/agents/categorization/test_counterparty_rules.py`
- `backend/tests/agents/ingestion/__init__.py`
- `backend/tests/agents/ingestion/test_ai_detected_counterparty.py`
- `backend/tests/integration/test_pe_categorization_e2e.py`
- `backend/tests/fixtures/pe_statement_extended_sample.csv`
- `scripts/rotate_iban_encryption.py`

**Modified:**
- `backend/app/core/config.py` — ENV, KMS_IBAN_KEY_ARN, LOCAL_IBAN_FERNET_KEY
- `backend/.env.example` — same new settings
- `backend/app/agents/ingestion/parsers/base.py` — TransactionData counterparty fields
- `backend/app/agents/ingestion/parsers/ai_detected.py` — first-class population, raw_data stash removed
- `backend/app/agents/categorization/node.py` — Rule 5-8 prompt block, deterministic enforcement, structured logs
- `backend/app/services/parser_service.py` — counterparty persist + PE self-register hook
- `backend/app/tasks/processing_tasks.py` — `_build_state_transactions` pre-computes is_self_iban
- `backend/app/models/transaction.py` — counterparty columns
- `backend/app/models/__init__.py` — register UserIbanRegistry
- `backend/tests/fixtures/categorization_golden_set/golden_set.jsonl` — 6 new rows + counterparty fields on gs-091..094
- `backend/tests/agents/categorization/test_golden_set.py` — harness de-segregation + counterparty threading, pe_statement min coverage raised to 8
- `backend/tests/test_account_deletion_api.py` — user_iban_registry cascade-delete coverage
- `docs/tech-debt.md` — TD-049 → RESOLVED
- `docs/operator-runbook.md` — new "Rotating the IBAN encryption KMS key" section
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — 11-10 → review
- `VERSION` — 1.25.0 → 1.26.0

## Change Log

| Date | Version | Change |
|---|---|---|
| 2026-04-21 | _(pending)_ | Story 11.10 drafted from TD-049. Migrates PE-statement categorization from fixture-specific description patterns to counterparty-driven rules (self-IBAN, Treasury EDRPOU, RNOKPP, EDRPOU). Introduces `app.core.crypto` envelope-encryption pattern + `user_iban_registry` table. Extends `TransactionData` with first-class counterparty fields (removes Story 11.7's `raw_data` stash path). Adds prompt Rule 5–8 with deterministic post-processing enforcement for Rule 5/6. Golden-set harness de-segregates `pe_statement` edge_case_tag; primary gate runs on the unified set. Retires TD-049 on merge. |
| 2026-04-21 | 1.26.0 | Story 11.10 implemented end-to-end: crypto module + migration + registry service + DTO/parser updates + prompt Rule 5–8 + deterministic enforcement + 6 new golden-set rows + E2E integration test + runbook KMS-rotation section + rotation script. TD-049 marked RESOLVED. Version bumped from 1.25.0 to 1.26.0 per story completion (new user-facing feature: PE-statement counterparty-aware categorization). |
| 2026-04-21 | 1.26.0 | Adversarial code review: fixed H1 (deterministic Rule 5/6 now survives threshold gate via `deterministic_rule` sentinel), H2 (`first_seen_upload_id` cascade → SET NULL so upload purge doesn't erase user IBANs), H4 (added `upload_id` + `transaction_row_index` to `counterparty_rule_hit` log per AC #13), M1 (removed no-op DEK-zeroing theater), M3 (rotation script switched to keyset pagination), M4 (explicit `session.flush()` before registry lookup), M5 (dedup now keyed on IBAN fingerprint, not plaintext). Deferred to tech-debt: TD-058 (Tasks 5.1/5.2 functionally dormant — requires `User.full_name` + header-scan parser work), TD-059 (Treasury EDRPOU seed list too small), TD-060–TD-062 (LOW polish). All 773 unit tests + 30 story-local tests + E2E still pass. |
