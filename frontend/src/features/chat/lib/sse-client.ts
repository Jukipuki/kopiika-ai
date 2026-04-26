import type { CitationDto, RefusalReason, StreamEvent } from "./chat-types";

// POST→ReadableStream SSE adapter. EventSource is GET-only, so we POST
// the message body and parse `text/event-stream` ourselves per
// docs/chat-sse-contract.md "Browser (EventSource + POST)" sketch.

export interface OpenStreamOptions {
  apiUrl: string;
  sessionId: string;
  token: string;
  message: string;
  signal?: AbortSignal;
}

export interface OpenStreamResult {
  events: AsyncGenerator<StreamEvent, void, void>;
  response: Response;
}

export class StreamHttpError extends Error {
  constructor(public status: number, public bodyText: string) {
    super(`HTTP ${status}`);
    this.name = "StreamHttpError";
  }
}

const KNOWN_EVENTS = new Set([
  "chat-open",
  "chat-thinking",
  "chat-token",
  "chat-citations",
  "chat-complete",
  "chat-refused",
]);

const REFUSAL_REASONS: ReadonlySet<RefusalReason> = new Set<RefusalReason>([
  "guardrail_blocked",
  "ungrounded",
  "rate_limited",
  "prompt_leak_detected",
  "tool_blocked",
  "transient_error",
]);

export function parseFrame(eventName: string, dataJson: string): StreamEvent | null {
  if (!KNOWN_EVENTS.has(eventName)) return null;
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(dataJson) as Record<string, unknown>;
  } catch {
    return null;
  }
  switch (eventName) {
    case "chat-open":
      return {
        type: "chat-open",
        correlationId: String(payload.correlationId ?? ""),
        sessionId: String(payload.sessionId ?? ""),
      };
    case "chat-thinking":
      return {
        type: "chat-thinking",
        toolName: String(payload.toolName ?? ""),
        hopIndex: Number(payload.hopIndex ?? 0),
      };
    case "chat-token":
      return { type: "chat-token", delta: String(payload.delta ?? "") };
    case "chat-citations":
      return {
        type: "chat-citations",
        citations: Array.isArray(payload.citations) ? (payload.citations as CitationDto[]) : [],
      };
    case "chat-complete":
      return {
        type: "chat-complete",
        inputTokens: Number(payload.inputTokens ?? 0),
        outputTokens: Number(payload.outputTokens ?? 0),
        sessionTurnCount: Number(payload.sessionTurnCount ?? 0),
        summarizationApplied: Boolean(payload.summarizationApplied),
        tokenSource: String(payload.tokenSource ?? ""),
        toolCallCount: Number(payload.toolCallCount ?? 0),
      };
    case "chat-refused": {
      const rawReason = String(payload.reason ?? "transient_error") as RefusalReason;
      const reason: RefusalReason = REFUSAL_REASONS.has(rawReason) ? rawReason : "transient_error";
      return {
        type: "chat-refused",
        error: "CHAT_REFUSED",
        reason,
        correlationId: String(payload.correlationId ?? ""),
        retryAfterSeconds: payload.retryAfterSeconds == null ? null : Number(payload.retryAfterSeconds),
      };
    }
  }
  return null;
}

async function* parseSseStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
): AsyncGenerator<StreamEvent, void, void> {
  const decoder = new TextDecoder();
  let buffer = "";
  let unknownWarned = false;

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIdx: number;
    while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
      const rawFrame = buffer.slice(0, sepIdx);
      buffer = buffer.slice(sepIdx + 2);
      if (!rawFrame.trim()) continue;
      // Skip comment-only frames (heartbeats: ":\n" or ": heartbeat\n").
      const lines = rawFrame.split("\n").filter((l) => !l.startsWith(":"));
      if (lines.length === 0) continue;

      let eventName = "message";
      const dataLines: string[] = [];
      for (const line of lines) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (dataLines.length === 0) continue;

      const dataJson = dataLines.join("\n");
      if (!KNOWN_EVENTS.has(eventName)) {
        if (!unknownWarned) {
          console.warn(`[chat-sse] unknown event name "${eventName}" — ignored (forward-compat)`);
          unknownWarned = true;
        }
        continue;
      }
      const evt = parseFrame(eventName, dataJson);
      if (evt) yield evt;
    }
  }
}

export async function openStream(opts: OpenStreamOptions): Promise<OpenStreamResult> {
  // Token goes in the Authorization header, not the URL. We use fetch +
  // ReadableStream rather than EventSource (which is GET-only and forces
  // JWT-in-query), so there's no reason to leak the token into access
  // logs / Referer / browser history.
  const url = `${opts.apiUrl}/api/v1/chat/sessions/${encodeURIComponent(opts.sessionId)}/turns/stream`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      Authorization: `Bearer ${opts.token}`,
    },
    body: JSON.stringify({ message: opts.message }),
    signal: opts.signal,
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new StreamHttpError(response.status, body);
  }
  if (!response.body) {
    throw new StreamHttpError(response.status, "missing body");
  }
  const reader = response.body.getReader();
  return { response, events: parseSseStream(reader) };
}

// Exposed for testing — feed a stream of raw SSE chunks (Uint8Array) and
// receive parsed StreamEvents. Mirrors the live wire reader path.
export async function* parseChunks(
  source: AsyncIterable<Uint8Array>,
): AsyncGenerator<StreamEvent, void, void> {
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      for await (const chunk of source) controller.enqueue(chunk);
      controller.close();
    },
  });
  yield* parseSseStream(stream.getReader());
}
