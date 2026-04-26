#!/usr/bin/env bash
# Story 10.9 — manual smoke test for the chat metric filters in
# observability-chat.tf. Runs `aws logs test-metric-filter` against
# representative log lines captured from the dev App Runner log group.
#
# This script is NOT wired into CI (no AWS creds in CI for this kind of
# smoke). Run locally before merge with the personal AWS profile:
#
#   AWS_PROFILE=personal bash infra/terraform/modules/app-runner/test_chat_metric_filters.sh
#
# Each block prints the matched events; an empty match list for any
# filter is a regression — investigate before merging.
#
# Captured log-line samples are inlined as compact JSON. Field shapes
# match `backend/app/core/logging.py`'s JsonFormatter output; if the
# formatter ever renames the `message` key, the patterns in this script
# AND in `observability-chat.tf` need to flip in lockstep.
set -euo pipefail

REGION="${AWS_REGION:-eu-central-1}"

run_filter() {
  local label="$1"
  local pattern="$2"
  local event="$3"
  echo "── ${label} ─────────────────────────────────────────────────────"
  echo "pattern: ${pattern}"
  aws logs test-metric-filter \
    --region "${REGION}" \
    --filter-pattern "${pattern}" \
    --log-event-messages "${event}"
  echo
}

# 1. chat.stream.opened
run_filter \
  "ChatStreamOpenedCount" \
  '{ $.message = "chat.stream.opened" }' \
  '{"message":"chat.stream.opened","level":"INFO","correlation_id":"abc-123","db_session_id":"00000000-0000-0000-0000-000000000001"}'

# 2. chat.stream.first_token (numeric extraction)
run_filter \
  "ChatStreamFirstTokenLatencyMs" \
  '{ $.message = "chat.stream.first_token" && $.ttfb_ms = * }' \
  '{"message":"chat.stream.first_token","level":"INFO","correlation_id":"abc-123","db_session_id":"00000000-0000-0000-0000-000000000001","ttfb_ms":820}'

# 3. chat.stream.completed
run_filter \
  "ChatStreamCompletedCount" \
  '{ $.message = "chat.stream.completed" }' \
  '{"message":"chat.stream.completed","level":"INFO","correlation_id":"abc-123","total_ms":2400,"input_tokens":120,"output_tokens":340,"tool_call_count":1}'

# 4. chat.stream.refused (any reason)
run_filter \
  "ChatStreamRefusedCount" \
  '{ $.message = "chat.stream.refused" }' \
  '{"message":"chat.stream.refused","level":"WARNING","correlation_id":"abc-123","reason":"input_blocked","exception_class":"ChatInputBlockedError"}'

# 5. chat.stream.refused (reason=ungrounded)
run_filter \
  "ChatStreamRefusedUngroundedCount" \
  '{ $.message = "chat.stream.refused" && $.reason = "ungrounded" }' \
  '{"message":"chat.stream.refused","level":"WARNING","correlation_id":"abc-123","reason":"ungrounded","exception_class":"ChatGuardrailInterventionError"}'

# 6. chat.stream.guardrail_intervened
run_filter \
  "ChatStreamGuardrailIntervenedCount" \
  '{ $.message = "chat.stream.guardrail_intervened" }' \
  '{"message":"chat.stream.guardrail_intervened","level":"WARNING","correlation_id":"abc-123","guardrail_action":"BLOCKED"}'

# 7. chat.stream.guardrail_detached
run_filter \
  "ChatStreamGuardrailDetachedCount" \
  '{ $.message = "chat.stream.guardrail_detached" }' \
  '{"message":"chat.stream.guardrail_detached","level":"WARNING","correlation_id":"abc-123"}'

# 8. chat.stream.finalizer_failed
run_filter \
  "ChatStreamFinalizerFailedCount" \
  '{ $.message = "chat.stream.finalizer_failed" }' \
  '{"message":"chat.stream.finalizer_failed","level":"ERROR","correlation_id":"abc-123","db_session_id":"00000000-0000-0000-0000-000000000001","error_class":"OperationalError","error_message":"connection lost","accumulated_char_len":420,"tool_results_count":1}'

# 9. chat.stream.disconnected
run_filter \
  "ChatStreamDisconnectedCount" \
  '{ $.message = "chat.stream.disconnected" }' \
  '{"message":"chat.stream.disconnected","level":"INFO","correlation_id":"abc-123","db_session_id":"00000000-0000-0000-0000-000000000001"}'

# 10. chat.stream.consent_drift
run_filter \
  "ChatStreamConsentDriftCount" \
  '{ $.message = "chat.stream.consent_drift" }' \
  '{"message":"chat.stream.consent_drift","level":"WARNING","correlation_id":"abc-123"}'

# 11. chat.input.blocked
run_filter \
  "ChatInputBlockedCount" \
  '{ $.message = "chat.input.blocked" }' \
  '{"message":"chat.input.blocked","level":"WARNING","correlation_id":"abc-123","user_id_hash":"a1b2c3d4e5f60718","reason":"jailbreak_pattern"}'

# 12. chat.canary.leaked
run_filter \
  "ChatCanaryLeakedCount" \
  '{ $.message = "chat.canary.leaked" }' \
  '{"message":"chat.canary.leaked","level":"ERROR","correlation_id":"abc-123","db_session_id":"00000000-0000-0000-0000-000000000001","canary_slot":"a","canary_prefix":"k0p1","canary_set_version_id":"v1","output_char_len":256,"output_prefix_hash":"deadbeef","finalizer_path":true}'

# 13. chat.canary.load_failed
run_filter \
  "ChatCanaryLoadFailedCount" \
  '{ $.message = "chat.canary.load_failed" }' \
  '{"message":"chat.canary.load_failed","level":"ERROR","correlation_id":"abc-123","user_id_hash":"a1b2c3d4e5f60718","error_class":"ClientError"}'

# 14. chat.tool.loop_exceeded
run_filter \
  "ChatToolLoopExceededCount" \
  '{ $.message = "chat.tool.loop_exceeded" }' \
  '{"message":"chat.tool.loop_exceeded","level":"WARNING","correlation_id":"abc-123","db_session_id":"00000000-0000-0000-0000-000000000001","tool_call_count":6}'

# 15. chat.tool.authorization_failed
run_filter \
  "ChatToolAuthorizationFailedCount" \
  '{ $.message = "chat.tool.authorization_failed" }' \
  '{"message":"chat.tool.authorization_failed","level":"WARNING","correlation_id":"abc-123","tool_name":"get_transactions","error_kind":"PermissionError"}'

# 16. chat.turn.completed (token spend, dimensioned by user_bucket)
run_filter \
  "ChatTurnTotalTokensUsed" \
  '{ $.message = "chat.turn.completed" && $.total_tokens_used = * && $.user_bucket = * }' \
  '{"message":"chat.turn.completed","level":"INFO","correlation_id":"abc-123","db_session_id":"00000000-0000-0000-0000-000000000001","user_id_hash":"a1b2c3d4e5f60718","user_bucket":"a","input_tokens":120,"output_tokens":340,"total_tokens_used":460,"session_turn_count":3,"summarization_applied":false,"tool_call_count":1,"tool_hop_count":1}'

# 17. chat.turn.completed (count)
run_filter \
  "ChatTurnCompletedCount" \
  '{ $.message = "chat.turn.completed" }' \
  '{"message":"chat.turn.completed","level":"INFO","correlation_id":"abc-123","db_session_id":"00000000-0000-0000-0000-000000000001","user_id_hash":"a1b2c3d4e5f60718","user_bucket":"a","input_tokens":120,"output_tokens":340,"total_tokens_used":460,"session_turn_count":3,"summarization_applied":false,"tool_call_count":1,"tool_hop_count":1}'

# 18. chat.citations.attached (citation_count) — single metric stream;
# P50/P95 are query-time statistics on `ChatCitationCount`.
run_filter \
  "ChatCitationCount (heartbeat 0)" \
  '{ $.message = "chat.citations.attached" && $.citation_count = * }' \
  '{"message":"chat.citations.attached","level":"INFO","correlation_id":"abc-123","db_session_id":"00000000-0000-0000-0000-000000000001","citation_count":0,"truncated":false,"contract_version":"v1"}'

run_filter \
  "ChatCitationCount (with citations)" \
  '{ $.message = "chat.citations.attached" && $.citation_count = * }' \
  '{"message":"chat.citations.attached","level":"INFO","correlation_id":"abc-123","db_session_id":"00000000-0000-0000-0000-000000000001","citation_count":3,"truncated":false,"contract_version":"v1"}'

# 19. chat.summarization.triggered
run_filter \
  "ChatSummarizationTriggeredCount" \
  '{ $.message = "chat.summarization.triggered" }' \
  '{"message":"chat.summarization.triggered","level":"INFO","correlation_id":"abc-123","db_session_id":"00000000-0000-0000-0000-000000000001","older_messages_count":12,"recent_messages_count":6}'

# 20. chat.summarization.failed
run_filter \
  "ChatSummarizationFailedCount" \
  '{ $.message = "chat.summarization.failed" }' \
  '{"message":"chat.summarization.failed","level":"ERROR","correlation_id":"abc-123","db_session_id":"00000000-0000-0000-0000-000000000001","dropped_turns_count":4,"error_class":"TransientLLMError"}'

echo "All filter patterns evaluated. Inspect each block's match output above; any empty list is a regression."
