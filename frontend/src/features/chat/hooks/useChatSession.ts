"use client";

import { useCallback, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ChatSession } from "../lib/chat-types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface CreateSessionResponse {
  sessionId: string;
  createdAt: string;
  consentVersionAtCreation?: string;
}

interface ListSessionsResponse {
  sessions: ChatSession[];
}

async function postJson<T>(path: string, token: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    const err = new Error(`HTTP ${res.status}`) as Error & {
      status: number;
      bodyText: string;
    };
    err.status = res.status;
    err.bodyText = text;
    throw err;
  }
  return (await res.json()) as T;
}

export function useChatSession() {
  const { data: session } = useSession();
  const token = session?.accessToken;
  const qc = useQueryClient();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  // Locally-tracked sessions created during this client lifetime. While
  // the GET /chat/sessions list endpoint isn't live (owned by Story
  // 10.10), the server returns nothing, so a freshly POSTed session would
  // disappear from the UI on the next refetch. We merge these in to keep
  // them visible until the real list endpoint exists and supersedes them.
  const [localSessions, setLocalSessions] = useState<ChatSession[]>([]);

  const sessionsQuery = useQuery<ListSessionsResponse>({
    queryKey: ["chat-sessions"],
    enabled: !!token,
    staleTime: 30_000,
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/v1/chat/sessions`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        // List endpoint may not exist (10.10) — return empty sessions list
        // to allow the UI to render and the user to create a session.
        if (res.status === 404 || res.status === 405) return { sessions: [] };
        throw new Error(`HTTP ${res.status}`);
      }
      return (await res.json()) as ListSessionsResponse;
    },
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      if (!token) throw new Error("not authenticated");
      return postJson<CreateSessionResponse>("/api/v1/chat/sessions", token);
    },
    onSuccess: (data) => {
      setActiveSessionId(data.sessionId);
      setLocalSessions((prev) =>
        prev.some((s) => s.sessionId === data.sessionId)
          ? prev
          : [...prev, { sessionId: data.sessionId, createdAt: data.createdAt, consentVersionAtCreation: data.consentVersionAtCreation }],
      );
      qc.invalidateQueries({ queryKey: ["chat-sessions"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (sessionId: string) => {
      if (!token) throw new Error("not authenticated");
      const res = await fetch(`${API_URL}/api/v1/chat/sessions/${sessionId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
      return sessionId;
    },
    onSuccess: (deletedId) => {
      if (activeSessionId === deletedId) setActiveSessionId(null);
      setLocalSessions((prev) => prev.filter((s) => s.sessionId !== deletedId));
      qc.invalidateQueries({ queryKey: ["chat-sessions"] });
    },
  });

  const mergedSessions = useMemo(() => {
    const server = sessionsQuery.data?.sessions ?? [];
    const seen = new Set(server.map((s) => s.sessionId));
    return [...server, ...localSessions.filter((s) => !seen.has(s.sessionId))];
  }, [sessionsQuery.data?.sessions, localSessions]);

  const selectSession = useCallback((id: string | null) => setActiveSessionId(id), []);

  return {
    sessions: mergedSessions,
    isLoading: sessionsQuery.isLoading,
    activeSessionId,
    selectSession,
    createSession: createMutation.mutateAsync,
    isCreating: createMutation.isPending,
    createError: createMutation.error as (Error & { status?: number }) | null,
    deleteSession: deleteMutation.mutateAsync,
    isDeleting: deleteMutation.isPending,
  };
}
