"use client";

import { useEffect, useRef } from "react";
import { useSession } from "next-auth/react";

export type SwipeDirection = "left" | "right" | "none";

export interface CardInteractionRecord {
  cardId: string;
  timeOnCardMs: number;
  educationExpanded: boolean;
  educationDepthReached: number;
  swipeDirection: SwipeDirection;
  cardPositionInFeed: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const BATCH_FLUSH_THRESHOLD = 5;
const BATCH_MAX_SIZE = 20;
const INTERACTIONS_PATH = "/api/v1/cards/interactions";

// Module-level state shared across all card instances on the page.
const pendingBatch: CardInteractionRecord[] = [];
const pendingSwipes = new Map<string, SwipeDirection>();
let beforeUnloadBound = false;

// Kept in a module-level ref so `beforeunload` can send an authenticated request.
let currentAccessToken: string | undefined;

/** CardStackNavigator calls this right before `setCurrentIndex(next)` to stamp
 * the direction that the outgoing card was swiped. Hook reads it on unmount. */
export function setPendingSwipeDirection(
  cardId: string,
  direction: SwipeDirection,
): void {
  pendingSwipes.set(cardId, direction);
}

function toCamelPayload(record: CardInteractionRecord) {
  return {
    cardId: record.cardId,
    timeOnCardMs: record.timeOnCardMs,
    educationExpanded: record.educationExpanded,
    educationDepthReached: record.educationDepthReached,
    swipeDirection: record.swipeDirection,
    cardPositionInFeed: record.cardPositionInFeed,
  };
}

function chunkForMaxSize(
  records: CardInteractionRecord[],
): CardInteractionRecord[][] {
  const chunks: CardInteractionRecord[][] = [];
  for (let i = 0; i < records.length; i += BATCH_MAX_SIZE) {
    chunks.push(records.slice(i, i + BATCH_MAX_SIZE));
  }
  return chunks;
}

async function flushBatchFetch(
  records: CardInteractionRecord[],
  accessToken: string | undefined,
): Promise<void> {
  if (!accessToken || records.length === 0) return;
  for (const chunk of chunkForMaxSize(records)) {
    try {
      await fetch(`${API_URL}${INTERACTIONS_PATH}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ interactions: chunk.map(toCamelPayload) }),
        keepalive: true,
      });
    } catch {
      // Fire-and-forget: telemetry should never surface an error to the user.
    }
  }
}

function flushBatchUnload(
  records: CardInteractionRecord[],
  accessToken: string | undefined,
): void {
  if (!accessToken || records.length === 0) return;
  for (const chunk of chunkForMaxSize(records)) {
    try {
      fetch(`${API_URL}${INTERACTIONS_PATH}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ interactions: chunk.map(toCamelPayload) }),
        keepalive: true,
      });
    } catch {
      // Best-effort during unload — nothing to do on failure.
    }
  }
}

function bindBeforeUnloadOnce(): void {
  if (beforeUnloadBound || typeof window === "undefined") return;
  window.addEventListener("beforeunload", () => {
    const drained = pendingBatch.splice(0, pendingBatch.length);
    flushBatchUnload(drained, currentAccessToken);
  });
  beforeUnloadBound = true;
}

function addToBatch(
  record: CardInteractionRecord,
  accessToken: string | undefined,
): void {
  pendingBatch.push(record);
  if (pendingBatch.length >= BATCH_FLUSH_THRESHOLD) {
    if (!accessToken) return; // keep records queued until auth is available
    const drained = pendingBatch.splice(0, pendingBatch.length);
    void flushBatchFetch(drained, accessToken);
  }
}

/** Internal test helpers — allow deterministic reset between test cases. */
export function __resetCardInteractionsForTesting(): void {
  pendingBatch.length = 0;
  pendingSwipes.clear();
  beforeUnloadBound = false;
  currentAccessToken = undefined;
}
export function __getPendingBatchForTesting(): CardInteractionRecord[] {
  return [...pendingBatch];
}

export function useCardInteractions(cardId: string, cardPositionInFeed: number) {
  const { data: session } = useSession();
  const startTimeRef = useRef<number>(performance.now());
  const educationExpandedRef = useRef(false);
  const educationDepthRef = useRef(0);

  const onEducationExpanded = (depth: number) => {
    educationExpandedRef.current = true;
    if (depth > educationDepthRef.current) {
      educationDepthRef.current = depth;
    }
  };

  useEffect(() => {
    currentAccessToken = session?.accessToken;
    bindBeforeUnloadOnce();
  }, [session?.accessToken]);

  useEffect(() => {
    startTimeRef.current = performance.now();
    return () => {
      const timeOnCardMs = Math.max(
        0,
        Math.round(performance.now() - startTimeRef.current),
      );
      const swipeDirection = pendingSwipes.get(cardId) ?? "none";
      pendingSwipes.delete(cardId);
      addToBatch(
        {
          cardId,
          timeOnCardMs,
          educationExpanded: educationExpandedRef.current,
          educationDepthReached: educationDepthRef.current,
          swipeDirection,
          cardPositionInFeed,
        },
        currentAccessToken,
      );
    };
    // Intentional: cleanup must read the original cardId/position captured at
    // mount. Re-running this effect on value change would lose the start-time
    // reference and cause a spurious flush.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { onEducationExpanded };
}
