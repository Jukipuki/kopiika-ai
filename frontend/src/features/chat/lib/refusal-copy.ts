import type { RefusalReason } from "./chat-types";

// Returns the i18n key under namespace "chat.refusal.<reason>.copy" for a
// given backend refusal reason. The actual UA/EN strings live in
// frontend/messages/{en,uk}.json. Forbidden-internal-terms lint
// (i18n.test.ts) protects the copy from leaking 'guardrail', 'grounding',
// 'canary', 'jailbreak', 'prompt injection'.

export function refusalCopyKey(reason: RefusalReason): string {
  return `refusal.${reason}.copy`;
}
