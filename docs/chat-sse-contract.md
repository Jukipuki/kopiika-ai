# Chat SSE Contract

**Authored:** Story 10.5 (2026-04-24).
**Consumers:** Story 10.7 (Chat UI / Vercel AI SDK), Story 10.8b (safety test runner), any future FE or third-party integrator of the chat streaming endpoint.
**Related:** [architecture.md §API Pattern — Chat Streaming](../_bmad-output/planning-artifacts/architecture.md), [10-3b-chat-ux-states-spec.md](../_bmad-output/implementation-artifacts/10-3b-chat-ux-states-spec.md) (refusal copy), [docs/adr/0004-chat-runtime-phasing.md](adr/0004-chat-runtime-phasing.md).

## Versioning posture

This contract is **not** semver'd. A breaking change (renaming or removing an event, changing the shape of an existing payload) requires a new story and an architecture amendment. New event names are additive — the frontend contract MUST be tolerant of unknown event names (silently ignore, do not error). Story 10.7 owns the unknown-event-name policy; this document documents the expectation.

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/chat/sessions` | Bearer (Cognito JWT, `Authorization: Bearer …`) | Create a session. Returns `{sessionId, createdAt, consentVersionAtCreation}`. |
| `POST` | `/api/v1/chat/sessions/{session_id}/turns/stream?token=<JWT>` | Query-string JWT | Stream one chat turn as SSE. Body: `{message: string}`. |
| `DELETE` | `/api/v1/chat/sessions/{session_id}` | Bearer | Terminate a session. `204 No Content`. |

Query-string auth on the stream endpoint is a constraint of `EventSource`, which does not support the `Authorization` header. Request body input is capped at `CHAT_MAX_INPUT_CHARS` (currently 4000) — over-cap requests return `422 CHAT_INPUT_TOO_LONG` **before** the stream opens; this is a client-shape failure, distinct from a `CHAT_REFUSED` refusal.

## Frame shape

All frames follow the standard SSE line shape:

```
event: <event-name>\ndata: <json>\n\n
```

Event names are kebab-case. Payload keys are camelCase (via the repo's `to_camel` alias convention). Heartbeats are `: heartbeat\n\n` comment-only frames emitted every 15 seconds of quiet time — ALB's 60s idle timeout is comfortably covered.

## Events (happy path)

The happy-path sequence is **always**:

```
chat-open
  → zero-or-more: chat-thinking
  → one-or-more:  chat-token
  → at-most-one:  chat-citations
  → chat-complete (terminal)
```

### `chat-open`

Fires exactly once as the first frame. Confirms the backend has authenticated, validated session ownership, attached the Bedrock Guardrail (if configured), and is about to dispatch the turn. Analogous to the first `pipeline-progress` frame in the jobs SSE contract.

```json
{"correlationId": "<uuid>", "sessionId": "<uuid>"}
```

### `chat-thinking`

Fires once per tool hop (one `get_transactions`, one `profile_lookup`, etc.), before the dispatcher runs. Client UI should render a lightweight "looking something up…" indicator and hide it when the next frame arrives. `ChatToolHopCompleted` is **not** surfaced (the end-of-hop is implicit in the next token or next `chat-thinking`).

```json
{"toolName": "get_transactions", "hopIndex": 1}
```

### `chat-token`

Fires for each token delta of the FINAL (plain-text) model iteration. Empty-string deltas are filtered at the backend, so `delta` is always at least one character. Deltas are append-only; there is no byte framing or incremental ID.

```json
{"delta": "Your "}
```

### `chat-citations`

Optional frame, fires at most once per turn after the final `chat-token`
and before `chat-complete`. Suppressed on all `chat-refused` paths and on
turns where no tools fired (the model answered from chat history alone).
Carries the structured citation payload that backs the chip row in the
chat UI (Story 10.7 consumer).

```json
{
  "citations": [
    {"kind": "transaction", "id": "<uuid>", "bookedAt": "2026-03-14",
     "description": "Coffee Shop", "amountKopiykas": -8500,
     "currency": "UAH", "categoryCode": "groceries",
     "label": "Coffee Shop · 2026-03-14"},
    {"kind": "category", "code": "groceries", "label": "Groceries"},
    {"kind": "profile_field", "field": "monthly_expenses_kopiykas",
     "value": 4530000, "currency": "UAH", "asOf": "2026-04-01",
     "label": "Monthly expenses (Apr 2026)"},
    {"kind": "rag_doc", "sourceId": "en/emergency-fund",
     "title": "en/emergency-fund", "snippet": "An emergency …",
     "similarity": 0.83, "label": "en/emergency-fund"}
  ]
}
```

Note on `rag_doc.title` / `rag_doc.label`: the corpus retriever
(`CorpusDocRow`) does not currently carry a human-friendly title, so the
assembler emits `title = label = source_id`. Tracked under
[`TD-125`](tech-debt.md#td-125--ragdoccitationtitle-degrades-to-source_id-until-corpusdocrow-carries-a-title-low);
the wire field stays `title: str` so adopting a real title later is
non-breaking.

Cap: at most **20 citations** per turn (server-side truncation, logged
at WARN if hit). Order: tool-call invocation order, then row order
within each tool, with first-occurrence dedup. Contract version pinned
in `CITATION_CONTRACT_VERSION` (currently `10.6b-v1`); bumps require a
new story.

#### Projection map (source of truth — Story 10.6b AC #2)

| Source tool | Source field path | Citation kind | Per-row citations produced |
|---|---|---|---|
| `get_transactions` | `payload.rows[*]` | `TransactionCitation` (one per row) + at most one `CategoryCitation` per **distinct** `category_code` across all rows | one TX citation per row; categories deduped across the whole turn |
| `get_profile` | `payload.summary.{monthly_income_kopiykas, monthly_expenses_kopiykas, savings_ratio, health_score}` | `ProfileFieldCitation` (one per *non-None* field) | up to 4 per profile call; only non-None fields cite |
| `get_profile` | `payload.category_breakdown[*].category_code` | `CategoryCitation` (deduped against transaction-derived categories) | one per breakdown row, deduped |
| `get_teaching_feed` | — | (none) | dropped; teaching-feed cards are not citable evidence in chat |
| `search_financial_corpus` | `payload.rows[*]` | `RagDocCitation` (one per row) | one per row; deduped by `source_id` across the turn |

Dedup keys (first-occurrence wins):
- `TransactionCitation`: `("transaction", id)`
- `CategoryCitation`: `("category", code)`
- `ProfileFieldCitation`: `("profile_field", field, as_of)`
- `RagDocCitation`: `("rag_doc", source_id)`

Failed tool calls (`ok=False`) are skipped silently.

### `chat-complete`

Fires exactly once as the terminal frame on a successful turn. The client uses this to close the `EventSource` and unlock the composer.

```json
{
  "inputTokens": 1284,
  "outputTokens": 87,
  "sessionTurnCount": 3,
  "summarizationApplied": false,
  "tokenSource": "model",
  "toolCallCount": 1
}
```

## Refusal envelope — `chat-refused`

When any typed refusal fires, the stream yields a **single** terminal `chat-refused` frame and returns. A `chat-complete` frame is never emitted alongside. The client dispatches on the event name.

```json
{
  "error": "CHAT_REFUSED",
  "reason": "<enum>",
  "correlationId": "<uuid>",
  "retryAfterSeconds": null
}
```

`reason` enum — exhaustive:

| `reason` | Triggered by | Client UX (see 10-3b) |
|---|---|---|
| `guardrail_blocked` | Input validator jailbreak / disallowed characters; Bedrock Guardrails content-filter / denied-topic / PII / word-filter intervention; consent-drift fallback | Neutral refusal copy; no retry button. "Try asking a different way." |
| `ungrounded` | Bedrock Guardrails contextual-grounding intervention (Story 10.6a tunes the threshold) | Neutral refusal. "I can only answer from your data. Try narrowing the question." |
| `prompt_leak_detected` | Canary detector fired on accumulated final text | Deliberately least-informative copy: "That message couldn't be processed. Please rephrase." (security-by-opacity). |
| `tool_blocked` | `ChatToolLoopExceededError` / `ChatToolNotAllowedError` / `ChatToolAuthorizationError` | Neutral refusal; no retry. |
| `rate_limited` | `ChatRateLimitedError` (Story 10.11 raises) | If `retryAfterSeconds` is non-null, countdown copy; else generic "try again later". |
| `transient_error` | `ChatTransientError` (Bedrock throttle / short-lived service error) | "Something went wrong. Try again in a moment." The client decides when to retry; the server does NOT silently retry. |

`correlationId` is **always** populated. It is the operator/support triage handle; the UI surfaces a truncated 8-char prefix with a clipboard affordance (per 10-3b §Correlation-ID Affordance).

`retryAfterSeconds` is populated ONLY for `reason=rate_limited` when the rate-limit middleware (Story 10.11) supplies it; `null` otherwise.

Deployment-misconfiguration failures (e.g. `ChatConfigurationError` — missing Guardrail ARN, IAM denied) do **not** emit a `chat-refused` frame. The stream either never opens (HTTP 500) or is aborted mid-flight. Operator pages via Story 10.9 are the escalation path; users see a dropped stream.

## Client-side error handling guidance

**Partial tokens + terminal refusal.** Under the canary-leak path, the client may receive `chat-token` frames followed by a terminal `chat-refused`. The UI contract is to **discard** the partially-rendered assistant text on refusal — a blocked turn never displays. The backend persists the text as `guardrail_action='blocked'` for forensic review; user-visible UI honors the refusal.

**Heartbeats.** Clients MUST tolerate `: heartbeat\n\n` comment-only frames at any point — they are not events. Some EventSource implementations suppress these automatically; custom parsers should skip any line starting with `:`.

**Disconnect semantics.** If the client closes the `EventSource` mid-stream, the backend honors cancellation: it commits whatever partial state ran (tool rows that completed, the assistant row if the final text flushed) and bumps `chat_sessions.last_active_at`. A dropped turn is indistinguishable in the DB from a completed turn.

## Example (curl + EventSource)

### Create a session

```bash
curl -X POST https://api.example.com/api/v1/chat/sessions \
     -H "Authorization: Bearer $JWT" \
     -H "Content-Type: application/json"
```

```json
{"sessionId": "3f2b…", "createdAt": "2026-04-24T…", "consentVersionAtCreation": "v1"}
```

### Stream a turn

```bash
curl -N -X POST "https://api.example.com/api/v1/chat/sessions/3f2b…/turns/stream?token=$JWT" \
     -H "Content-Type: application/json" \
     -d '{"message": "What did I spend on groceries in March?"}'
```

```
event: chat-open
data: {"correlationId":"8b…","sessionId":"3f2b…"}

event: chat-thinking
data: {"toolName":"get_transactions","hopIndex":1}

event: chat-token
data: {"delta":"In "}

event: chat-token
data: {"delta":"March "}

…

event: chat-complete
data: {"inputTokens":1284,"outputTokens":87,"sessionTurnCount":3,"summarizationApplied":false,"tokenSource":"model","toolCallCount":1}
```

### Browser (EventSource + POST)

`EventSource` is GET-only, so modern chat clients open the stream with `fetch` + a `ReadableStream` parser (the Vercel AI SDK's default). Sketch:

```ts
const res = await fetch(
  `/api/v1/chat/sessions/${sessionId}/turns/stream?token=${token}`,
  {method: "POST", headers: {"Content-Type": "application/json"},
   body: JSON.stringify({message})}
);
const reader = res.body!.getReader();
const decoder = new TextDecoder();
for (;;) {
  const {value, done} = await reader.read();
  if (done) break;
  // parse SSE frames from decoder.decode(value, {stream: true})
  // dispatch on event name per the table above
}
```

Story 10.7 will wire the Vercel AI SDK adapter; this document pins only the wire-format contract.

## Observability cross-reference

Every frame on a turn carries the same `correlationId` that stamps these backend logs — all namespaced `chat.stream.*`:

| Log event | When | Level |
|---|---|---|
| `chat.stream.opened` | After auth + ownership, before `send_turn_stream` | INFO |
| `chat.stream.first_token` | First `chat-token` frame | INFO (carries `ttfb_ms` — Story 10.9 SLO) |
| `chat.stream.completed` | On `chat-complete` | INFO |
| `chat.stream.refused` | On `chat-refused` | INFO (WARN for `transient_error`, ERROR for consent_drift) |
| `chat.stream.disconnected` | Client dropped mid-stream | INFO |
| `chat.stream.guardrail_detached` | `guardrail_id=None` path hit | WARN |
| `chat.stream.consent_drift` | `ChatConsentRequiredError` at turn time (should be impossible) | ERROR |
| `chat.citations.attached` | After the canary scan passes on the happy path | INFO (carries `citation_count` + `citation_kinds_histogram` + `contract_version`) |

Story 10.9 turns these into CloudWatch metric filters + alarms.
