// Chat wire types — mirror docs/chat-sse-contract.md (10.5/10.5a) and
// _bmad-output/implementation-artifacts/10-6b-citation-payload-data-refs.md.
// These are the *FE* shapes; backend authority lives in app/agents/chat/.

export type RefusalReason =
  | "guardrail_blocked"
  | "ungrounded"
  | "rate_limited"
  | "prompt_leak_detected"
  | "tool_blocked"
  | "transient_error";

export interface TransactionCitation {
  kind: "transaction";
  id: string;
  bookedAt: string;
  description: string;
  amountKopiykas: number;
  currency: string;
  categoryCode: string;
  label: string;
}

export interface CategoryCitation {
  kind: "category";
  code: string;
  label: string;
}

export interface ProfileFieldCitation {
  kind: "profile_field";
  field: string;
  value: number | string | null;
  currency?: string | null;
  asOf?: string | null;
  label: string;
}

export interface RagDocCitation {
  kind: "rag_doc";
  sourceId: string;
  title: string;
  snippet: string;
  similarity: number;
  label: string;
}

export type CitationDto =
  | TransactionCitation
  | CategoryCitation
  | ProfileFieldCitation
  | RagDocCitation;

export interface ChatOpenFrame {
  type: "chat-open";
  correlationId: string;
  sessionId: string;
}

export interface ChatThinkingFrame {
  type: "chat-thinking";
  toolName: string;
  hopIndex: number;
}

export interface ChatTokenFrame {
  type: "chat-token";
  delta: string;
}

export interface ChatCitationsFrame {
  type: "chat-citations";
  citations: CitationDto[];
}

export interface ChatCompleteFrame {
  type: "chat-complete";
  inputTokens: number;
  outputTokens: number;
  sessionTurnCount: number;
  summarizationApplied: boolean;
  tokenSource: string;
  toolCallCount: number;
}

export interface ChatRefusedFrame {
  type: "chat-refused";
  error: "CHAT_REFUSED";
  reason: RefusalReason;
  correlationId: string;
  retryAfterSeconds: number | null;
}

export type StreamEvent =
  | ChatOpenFrame
  | ChatThinkingFrame
  | ChatTokenFrame
  | ChatCitationsFrame
  | ChatCompleteFrame
  | ChatRefusedFrame;

export interface ChatSession {
  sessionId: string;
  createdAt: string;
  consentVersionAtCreation?: string;
  // Local-only — server never returns; FE caches user-friendly title from
  // first message preview for SessionList rendering.
  title?: string;
  lastActiveAt?: string;
}

export type TurnRole = "user" | "assistant";

export interface ChatTurn {
  id: string;
  role: TurnRole;
  text: string;
  createdAt: string;
  // assistant-only:
  streaming?: boolean;
  citations?: CitationDto[];
  refusal?: { reason: RefusalReason; correlationId: string; retryAfterSeconds: number | null };
  thinkingTool?: string | null;
  // diagnostic:
  correlationId?: string;
}

export const CITATION_CONTRACT_VERSION = "10.6b-v1";
