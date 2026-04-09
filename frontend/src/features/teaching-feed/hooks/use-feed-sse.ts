"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const INITIAL_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30000;
const MAX_RECONNECT_ATTEMPTS = 10;

export function useFeedSSE(jobId: string | null, accessToken: string | undefined) {
  const queryClient = useQueryClient();
  const [pendingInsightIds, setPendingInsightIds] = useState<string[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const terminalRef = useRef(false);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const jobIdRef = useRef(jobId);

  jobIdRef.current = jobId;

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    esRef.current?.close();
    esRef.current = null;
  }, []);

  const connect = useCallback(() => {
    const currentJobId = jobIdRef.current;
    if (!currentJobId || !accessToken) return;

    cleanup();
    setIsStreaming(true);

    const url = `${API_URL}/api/v1/jobs/${currentJobId}/stream?token=${encodeURIComponent(accessToken)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener("pipeline-progress", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        setMessage(data.message ?? null);
      } catch {
        // Ignore malformed SSE payloads
      }
    });

    es.addEventListener("insight-ready", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        if (data.insightId) {
          setPendingInsightIds((prev) => [...prev, data.insightId]);
        }
      } catch {
        // Ignore malformed SSE payloads
      }
    });

    es.addEventListener("job-complete", () => {
      terminalRef.current = true;
      setIsStreaming(false);
      setMessage(null);
      queryClient.invalidateQueries({ queryKey: ["teaching-feed"] });
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      cleanup();
    });

    es.addEventListener("job-failed", () => {
      terminalRef.current = true;
      setIsStreaming(false);
      setMessage(null);
      setPendingInsightIds([]);
      cleanup();
    });

    es.onerror = () => {
      esRef.current?.close();
      esRef.current = null;

      if (terminalRef.current || reconnectAttemptRef.current >= MAX_RECONNECT_ATTEMPTS) {
        setIsStreaming(false);
        return;
      }

      const delay = Math.min(
        INITIAL_RECONNECT_DELAY * 2 ** reconnectAttemptRef.current,
        MAX_RECONNECT_DELAY,
      );
      reconnectAttemptRef.current++;

      reconnectTimerRef.current = setTimeout(() => {
        if (jobIdRef.current === currentJobId) {
          connect();
        }
      }, delay);
    };
  }, [accessToken, cleanup, queryClient]);

  useEffect(() => {
    if (!jobId || !accessToken) {
      cleanup();
      setIsStreaming(false);
      setPendingInsightIds([]);
      setMessage(null);
      return;
    }

    terminalRef.current = false;
    reconnectAttemptRef.current = 0;
    setPendingInsightIds([]);
    setMessage(null);
    connect();

    return cleanup;
  }, [jobId, accessToken, connect, cleanup]);

  return { pendingInsightIds, isStreaming, message };
}
