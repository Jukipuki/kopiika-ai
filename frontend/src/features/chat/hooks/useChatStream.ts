"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { useSession } from "next-auth/react";
import { openStream, StreamHttpError } from "../lib/sse-client";
import type {
  CitationDto,
  RefusalReason,
  StreamEvent,
} from "../lib/chat-types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ChatTurnState {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt: string;
  streaming?: boolean;
  thinkingTool?: string | null;
  citations?: CitationDto[];
  refusal?: {
    reason: RefusalReason;
    correlationId: string;
    retryAfterSeconds: number | null;
    // Wall-clock epoch ms at which a rate-limited cooldown ends. Set when
    // the refusal frame arrives; consumed by ChatScreen to drive the
    // composer-disabled gate without re-issuing per-second state ticks
    // through the reducer.
    cooldownEndsAt?: number;
  };
  correlationId?: string;
  // Pre-stream HTTP error attached to the user's bubble (composer-side error
  // banner reads this; assistant bubble is suppressed).
  preStreamError?: { status: number; kind: "input_too_long" | "consent_required" | "other" };
  // Mid-stream disconnect — bubble retains partial text + retry CTA.
  disconnected?: boolean;
}

export interface ChatStreamState {
  turns: ChatTurnState[];
  inFlight: boolean;
}

type Action =
  | { type: "USER_SEND"; turn: ChatTurnState }
  | { type: "ASSISTANT_OPEN"; turn: ChatTurnState }
  | { type: "FRAME"; event: StreamEvent }
  | { type: "DISCONNECT"; turnId: string }
  | { type: "PRE_STREAM_ERROR"; turnId: string; status: number }
  | { type: "RESET"; turns: ChatTurnState[] };

function reducer(state: ChatStreamState, action: Action): ChatStreamState {
  switch (action.type) {
    case "USER_SEND":
      return { ...state, turns: [...state.turns, action.turn], inFlight: true };
    case "ASSISTANT_OPEN":
      return { ...state, turns: [...state.turns, action.turn] };
    case "FRAME": {
      const turns = [...state.turns];
      const lastIdx = turns.findLastIndex((t) => t.role === "assistant" && t.streaming);
      if (lastIdx === -1) return state;
      const turn = { ...turns[lastIdx] };
      switch (action.event.type) {
        case "chat-open":
          turn.correlationId = action.event.correlationId;
          turn.streaming = true;
          break;
        case "chat-thinking":
          turn.thinkingTool = action.event.toolName;
          break;
        case "chat-token":
          turn.text += action.event.delta;
          turn.thinkingTool = null;
          break;
        case "chat-citations":
          turn.citations = action.event.citations;
          break;
        case "chat-complete":
          turn.streaming = false;
          break;
        case "chat-refused": {
          // Refusal mutual-exclusion: drop any pending citations and
          // discard partial text per docs/chat-sse-contract.md
          // "Partial tokens + terminal refusal".
          turn.text = "";
          turn.citations = undefined;
          turn.streaming = false;
          const ras = action.event.retryAfterSeconds;
          turn.refusal = {
            reason: action.event.reason,
            correlationId: action.event.correlationId,
            retryAfterSeconds: ras,
            cooldownEndsAt:
              action.event.reason === "rate_limited" && ras != null && ras > 0
                ? Date.now() + ras * 1000
                : undefined,
          };
          break;
        }
      }
      turns[lastIdx] = turn;
      const stillStreaming = turns.some((t) => t.role === "assistant" && t.streaming);
      return { ...state, turns, inFlight: stillStreaming };
    }
    case "DISCONNECT": {
      const turns = state.turns.map((t) =>
        t.id === action.turnId ? { ...t, streaming: false, disconnected: true } : t,
      );
      return { ...state, turns, inFlight: false };
    }
    case "PRE_STREAM_ERROR": {
      const turns = state.turns.map((t) => {
        if (t.id !== action.turnId) return t;
        const kind: "input_too_long" | "consent_required" | "other" =
          action.status === 422
            ? "input_too_long"
            : action.status === 403
              ? "consent_required"
              : "other";
        return { ...t, preStreamError: { status: action.status, kind } };
      });
      return { ...state, turns, inFlight: false };
    }
    case "RESET":
      return { turns: action.turns, inFlight: false };
  }
}

function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `tmp-${Math.random().toString(36).slice(2)}-${Date.now()}`;
}

export function useChatStream(sessionId: string | null) {
  const { data: session } = useSession();
  const token = session?.accessToken;
  const [state, dispatch] = useReducer(reducer, { turns: [], inFlight: false });
  const abortRef = useRef<AbortController | null>(null);
  const lastUserMessageRef = useRef<string>("");

  const send = useCallback(
    async (message: string, overrideSessionId?: string) => {
      // overrideSessionId lets ChatScreen dispatch a send right after a
      // just-created session resolves, without waiting for the next render
      // to rebind the closure (fixes the "first message after auto-create
      // silently dropped" race).
      const sid = overrideSessionId ?? sessionId;
      if (!sid || !token || !message.trim() || state.inFlight) return;
      lastUserMessageRef.current = message;

      const userTurn: ChatTurnState = {
        id: uuid(),
        role: "user",
        text: message,
        createdAt: new Date().toISOString(),
      };
      dispatch({ type: "USER_SEND", turn: userTurn });

      const assistantTurn: ChatTurnState = {
        id: uuid(),
        role: "assistant",
        text: "",
        createdAt: new Date().toISOString(),
        streaming: true,
      };
      dispatch({ type: "ASSISTANT_OPEN", turn: assistantTurn });

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      try {
        const { events } = await openStream({
          apiUrl: API_URL,
          sessionId: sid,
          token,
          message,
          signal: ctrl.signal,
        });
        for await (const evt of events) {
          dispatch({ type: "FRAME", event: evt });
        }
        // Stream ended without chat-complete or chat-refused — treat as disconnect.
        dispatch({ type: "DISCONNECT", turnId: assistantTurn.id });
      } catch (err: unknown) {
        if ((err as { name?: string })?.name === "AbortError") {
          dispatch({ type: "DISCONNECT", turnId: assistantTurn.id });
          return;
        }
        if (err instanceof StreamHttpError) {
          dispatch({ type: "PRE_STREAM_ERROR", turnId: assistantTurn.id, status: err.status });
          return;
        }
        dispatch({ type: "DISCONNECT", turnId: assistantTurn.id });
      }
    },
    [sessionId, token, state.inFlight],
  );

  const retryLast = useCallback(() => {
    if (lastUserMessageRef.current) void send(lastUserMessageRef.current);
  }, [send]);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: "RESET", turns: [] });
  }, []);

  // Abort any in-flight stream when the consumer unmounts so the fetch +
  // ReadableStream reader don't leak past the chat surface lifecycle.
  useEffect(() => () => abortRef.current?.abort(), []);

  return { ...state, send, retryLast, reset };
}
