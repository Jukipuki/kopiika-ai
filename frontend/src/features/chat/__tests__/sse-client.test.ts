import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { parseFrame, parseChunks, openStream, StreamHttpError } from "../lib/sse-client";

const enc = new TextEncoder();

async function* asyncFromChunks(chunks: string[]): AsyncIterable<Uint8Array> {
  for (const c of chunks) yield enc.encode(c);
}

describe("parseFrame", () => {
  it("parses chat-open", () => {
    const e = parseFrame("chat-open", JSON.stringify({ correlationId: "c1", sessionId: "s1" }));
    expect(e).toEqual({ type: "chat-open", correlationId: "c1", sessionId: "s1" });
  });

  it("parses chat-token with delta", () => {
    expect(parseFrame("chat-token", '{"delta":"Hi "}')).toEqual({ type: "chat-token", delta: "Hi " });
  });

  it("parses chat-citations array", () => {
    const cites = [{ kind: "category", code: "groceries", label: "Groceries" }];
    const e = parseFrame("chat-citations", JSON.stringify({ citations: cites }));
    expect(e?.type).toBe("chat-citations");
    if (e?.type === "chat-citations") expect(e.citations).toEqual(cites);
  });

  it("clamps unknown refusal reasons to transient_error", () => {
    const e = parseFrame("chat-refused", JSON.stringify({ reason: "made_up", correlationId: "c2" }));
    expect(e?.type).toBe("chat-refused");
    if (e?.type === "chat-refused") expect(e.reason).toBe("transient_error");
  });

  it("returns null for unknown event names", () => {
    expect(parseFrame("chat-mystery", "{}")).toBeNull();
  });

  it("returns null for invalid JSON", () => {
    expect(parseFrame("chat-token", "not json")).toBeNull();
  });
});

describe("parseChunks (FSM)", () => {
  it("parses a well-formed sequence", async () => {
    const wire =
      "event: chat-open\ndata: {\"correlationId\":\"c\",\"sessionId\":\"s\"}\n\n" +
      "event: chat-thinking\ndata: {\"toolName\":\"get_transactions\",\"hopIndex\":1}\n\n" +
      "event: chat-token\ndata: {\"delta\":\"Hi \"}\n\n" +
      "event: chat-token\ndata: {\"delta\":\"there\"}\n\n" +
      "event: chat-complete\ndata: {\"inputTokens\":10,\"outputTokens\":2,\"sessionTurnCount\":1,\"summarizationApplied\":false,\"tokenSource\":\"model\",\"toolCallCount\":1}\n\n";
    const events = [];
    for await (const e of parseChunks(asyncFromChunks([wire]))) events.push(e);
    expect(events.map((e) => e.type)).toEqual([
      "chat-open",
      "chat-thinking",
      "chat-token",
      "chat-token",
      "chat-complete",
    ]);
  });

  it("tolerates heartbeat comment-only frames", async () => {
    const wire =
      ": heartbeat\n\n" +
      "event: chat-open\ndata: {\"correlationId\":\"c\",\"sessionId\":\"s\"}\n\n" +
      ":\n\n";
    const events = [];
    for await (const e of parseChunks(asyncFromChunks([wire]))) events.push(e);
    expect(events.map((e) => e.type)).toEqual(["chat-open"]);
  });

  it("ignores unknown event names with a single warn", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const wire =
      "event: chat-mystery\ndata: {}\n\n" +
      "event: chat-mystery\ndata: {}\n\n" +
      "event: chat-token\ndata: {\"delta\":\"x\"}\n\n";
    const events = [];
    for await (const e of parseChunks(asyncFromChunks([wire]))) events.push(e);
    expect(events.map((e) => e.type)).toEqual(["chat-token"]);
    expect(warn).toHaveBeenCalledTimes(1);
    warn.mockRestore();
  });

  it("handles split chunks (frame straddles a boundary)", async () => {
    const a = "event: chat-token\ndata: {\"delt";
    const b = "a\":\"hello\"}\n\n";
    const events = [];
    for await (const e of parseChunks(asyncFromChunks([a, b]))) events.push(e);
    expect(events).toHaveLength(1);
    if (events[0].type === "chat-token") expect(events[0].delta).toBe("hello");
  });
});

describe("openStream HTTP error handling", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("throws StreamHttpError on 422 (input too long)", async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response("input too long", { status: 422 }),
    );
    await expect(
      openStream({ apiUrl: "http://x", sessionId: "s", token: "t", message: "a".repeat(5000) }),
    ).rejects.toBeInstanceOf(StreamHttpError);
  });

  it("throws StreamHttpError on 403 (consent required)", async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response("forbidden", { status: 403 }),
    );
    await expect(
      openStream({ apiUrl: "http://x", sessionId: "s", token: "t", message: "ok" }),
    ).rejects.toMatchObject({ status: 403 });
  });
});
