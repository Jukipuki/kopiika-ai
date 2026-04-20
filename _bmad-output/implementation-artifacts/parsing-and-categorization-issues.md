Problem Description & Recommended Solution
For: Architect review
Area: Transaction ingestion pipeline — parsing and categorization
Status: Known bugs fixed (hotfix shipped); root causes require proper rework

Background
The pipeline currently processes bank statements in two stages: (1) a CSV parser extracts raw transactions, (2) a categorization node assigns a spending category to each transaction. Both stages have structural weaknesses that produce incorrect financial profiles and insight cards.

Problem 1 — Categorization: Insufficient Semantic Granularity
Current state
Categorization uses a two-pass strategy: MCC code lookup (deterministic, ~60% coverage), then LLM batch inference for the remainder. The LLM receives only description and amount — no MCC, no transaction direction, no contextual signals.

Issues
1a. Transfer transactions corrupt financial metrics.
MCC 4829 (Wire Transfer Money Orders) covers semantically distinct transaction types: self-transfers between own accounts, capital movements to savings/investment accounts, and P2P payments to individuals. All three were previously unmapped in the MCC table, causing the LLM to classify them as finance. This inflated Finance category spending by including income transfers as spending (bug: abs() used on all transactions), and caused Finance to disappear from the category breakdown (bug: net-positive after mixing income and expense).

Both symptoms were hotfixed. The underlying cause — insufficient category granularity — remains.

1b. The LLM operates without enough context.
The LLM prompt provides description and amount only. It cannot distinguish between:

"Deposit top-up" -₴199,980 → capital movement to a deposit (savings)
"Oksana Medovoi" -₴15,000 → P2P transfer to an individual
"From UAH account" +₴10,000 → self-transfer (income, not a purchase)
Both the first two are currently categorized as transfers after the hotfix — semantically incorrect.

1c. No feedback loop on low-confidence categorizations.
Transactions below the confidence threshold are silently set to uncategorized. There is no mechanism to surface, review, or improve these over time.

Recommended solution
Phase 1 — Category schema extension.
Add savings and transfers_p2p to VALID_CATEGORIES. Define what belongs in each:

savings — capital movements to deposit, investment, or savings accounts (large outbound transfers with specific description patterns)
transfers_p2p — outbound payments to named individuals
transfers — residual inter-account movements not matching the above
Phase 2 — Description-pattern pre-pass.
Before the MCC pass, run a lightweight rule-based classifier on description text for the transaction types that are reliably identifiable by pattern. This handles high-volume, high-confidence cases (self-transfers, deposits) without LLM cost and without relying on MCC availability. Rules are explicit, auditable, and maintainable.

Phase 3 — Enriched LLM prompt.
For transactions that reach the LLM pass, provide: description, amount (with sign), MCC code (where available), and transaction direction (debit/credit). Add savings and transfers_p2p to the category list in the prompt. Include few-shot examples for the new categories.

Open questions for architect:

Should savings outflows be excluded from spending analysis entirely (like income is), or shown as a separate breakdown category?
For transfers_p2p, should the system attempt to identify recurring P2P recipients as a separate insight signal?
What is the acceptable confidence floor before a transaction is flagged for user review vs. silently left as uncategorized?
Problem 2 — Parsing: Brittle Heuristic Format Detection
Current state
Three separate parsers exist: monobank.py, privatbank.py, and generic.py. Each uses hardcoded column name detection and fixed date format lists. The generic parser is a best-effort fallback with no guarantee of correctness.

Issues
2a. Column detection is fragile.
Parsers match column names by keyword search against a fixed list. Any column rename, header translation (e.g., bank changes language), or reordering silently produces corrupt data — wrong amounts, wrong dates, or missed columns — with no runtime error.

2b. New banks require code changes.
Every new bank statement format requires a developer to write or extend a parser. There is no self-service path.

2c. Encoding variations are unhandled.
The Monobank statement contains UTF-8 Cyrillic text that arrives as mojibake when opened with the wrong encoding. Merchant names used for supplemental LLM categorization are garbage strings in these cases, degrading categorization quality silently.

2d. No structural validation on parsed output.
After parsing, there is no assertion that amounts have correct signs, dates fall within a plausible range, or required fields are non-null. Corrupt rows pass through to the financial profile.

Recommended solution
Phase 1 — AI-assisted schema detection (one call per new format).
When a file arrives from an unknown source, send the header row + 3 sample rows to the LLM and ask it to return a structured column mapping: {date, amount, description, currency, mcc, ...}. Apply that mapping deterministically to parse all rows. The LLM reasons about structure, not values — hallucination risk is minimal and the output is a simple config, not financial data.

Cache the detected schema by header fingerprint (hash of normalized column names) so repeat uploads from the same bank incur zero LLM cost.

Known banks (Monobank, PrivatBank) retain their existing deterministic parsers for reliability and zero cost on the happy path. The AI detection path is the fallback for unknown formats and for known formats where detection fails.

Phase 2 — Post-parse validation layer.
After any parser runs, validate the output: amount signs match expected debit/credit indicators, dates fall within ±5 years of today, description is non-null, no duplicate rows exceed a threshold. Reject or flag rows that fail validation before they reach the categorization node. Surface a structured error to the user rather than silently passing bad data.

Phase 3 — Encoding detection.
Use chardet or charset-normalizer to detect file encoding before parsing. Log the detected encoding and fall back to UTF-8 with replacement characters rather than silent mojibake. Flag statements where >5% of descriptions contain replacement characters.

Open questions for architect:

Should the schema detection result be persisted to a bank_format_registry table for operator review and override?
What is the user-facing experience when post-parse validation rejects rows? Partial import with warnings, or full rejection?
Should the generic parser be deprecated once AI schema detection is in place, or kept as a further fallback?
Dependencies & Risks
Both problems are independent and can be designed and implemented in parallel.
The categorization changes affect the financial profile and all downstream insight generation — schema changes to VALID_CATEGORIES and category label changes require a data migration strategy for existing transactions.
The parsing changes affect the ingestion boundary — validation failures will surface errors that currently pass silently, which may reveal data quality issues in existing uploaded statements.