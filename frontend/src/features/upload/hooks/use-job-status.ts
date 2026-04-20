"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useSession } from "next-auth/react";
import type { JobStatusState, SSEEvent } from "../types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const INITIAL_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30000;
const MAX_RECONNECT_ATTEMPTS = 10;

const initialState: JobStatusState = {
  status: "idle",
  step: null,
  progress: 0,
  message: null,
  error: null,
  result: null,
  isConnected: false,
  isRetryable: true,
  retryCount: 0,
};

export function useJobStatus(jobId: string | null): JobStatusState & { retry: () => void } {
  const { data: session } = useSession();
  const [state, setState] = useState<JobStatusState>(initialState);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const jobIdRef = useRef(jobId);
  const terminalRef = useRef(false);

  // Keep ref in sync
  jobIdRef.current = jobId;

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    const currentJobId = jobIdRef.current;
    const token = session?.accessToken;
    if (!currentJobId || !token) return;

    cleanup();
    setState((prev) => ({ ...prev, status: "connecting", isConnected: false }));

    const url = `${API_URL}/api/v1/jobs/${currentJobId}/stream?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => {
      reconnectAttemptRef.current = 0;
      setState((prev) => ({ ...prev, isConnected: true, status: prev.status === "connecting" ? "processing" : prev.status }));
    };

    es.addEventListener("pipeline-progress", (e: MessageEvent) => {
      const data = JSON.parse(e.data) as SSEEvent;
      if (data.event === "pipeline-progress") {
        setState((prev) => ({
          ...prev,
          status: "processing",
          step: data.step,
          progress: data.progress,
          message: data.message ?? null,
          isConnected: true,
        }));
      }
    });

    es.addEventListener("job-complete", (e: MessageEvent) => {
      const data = JSON.parse(e.data) as SSEEvent;
      if (data.event === "job-complete") {
        terminalRef.current = true;
        setState({
          status: "completed",
          step: null,
          progress: 100,
          message: null,
          error: null,
          result: {
            totalInsights: data.totalInsights,
            duplicatesSkipped: data.duplicatesSkipped,
            newTransactions: data.newTransactions,
            bankName: data.bankName ?? null,
            transactionCount: data.transactionCount ?? data.newTransactions,
            dateRange: data.dateRange ?? null,
            rejectedRows: data.rejectedRows ?? [],
            warnings: data.warnings ?? [],
            schemaDetectionSource: data.schemaDetectionSource,
            mojibakeDetected: data.mojibakeDetected ?? false,
          },
          isConnected: false,
          isRetryable: false,
          retryCount: 0,
        });
        es.close();
        eventSourceRef.current = null;
      }
    });

    es.addEventListener("job-failed", (e: MessageEvent) => {
      const data = JSON.parse(e.data) as SSEEvent;
      if (data.event === "job-failed") {
        terminalRef.current = true;
        setState({
          status: "failed",
          step: null,
          progress: 0,
          message: null,
          error: data.error,
          result: null,
          isConnected: false,
          isRetryable: data.isRetryable ?? true,
          retryCount: 0,
        });
        es.close();
        eventSourceRef.current = null;
      }
    });

    es.addEventListener("job-retrying", (e: MessageEvent) => {
      const data = JSON.parse(e.data) as SSEEvent;
      if (data.event === "job-retrying") {
        setState((prev) => ({
          ...prev,
          status: "retrying",
          retryCount: data.retryCount,
          isConnected: true,
        }));
      }
    });

    es.addEventListener("job-resumed", (e: MessageEvent) => {
      const data = JSON.parse(e.data) as SSEEvent;
      if (data.event === "job-resumed") {
        setState((prev) => ({
          ...prev,
          status: "processing",
          step: data.resumeFromStep,
          error: null,
          isConnected: true,
        }));
      }
    });

    es.onerror = () => {
      es.close();
      eventSourceRef.current = null;
      setState((prev) => ({ ...prev, isConnected: false }));

      // Don't reconnect if terminal state already reached or max attempts exceeded
      if (terminalRef.current || reconnectAttemptRef.current >= MAX_RECONNECT_ATTEMPTS) {
        return;
      }

      const delay = Math.min(
        INITIAL_RECONNECT_DELAY * 2 ** reconnectAttemptRef.current,
        MAX_RECONNECT_DELAY,
      );
      reconnectAttemptRef.current++;

      reconnectTimerRef.current = setTimeout(() => {
        // Only reconnect if jobId hasn't changed and we haven't reached terminal state
        if (jobIdRef.current === currentJobId) {
          connect();
        }
      }, delay);
    };
  }, [session?.accessToken, cleanup]);

  // Connect when jobId changes
  useEffect(() => {
    if (!jobId) {
      cleanup();
      setState(initialState);
      return;
    }

    reconnectAttemptRef.current = 0;
    terminalRef.current = false;
    connect();

    return cleanup;
  }, [jobId, connect, cleanup]);

  const retry = useCallback(() => {
    reconnectAttemptRef.current = 0;
    terminalRef.current = false;
    setState((prev) => ({ ...prev, error: null, status: "idle" }));
    connect();
  }, [connect]);

  return { ...state, retry };
}
