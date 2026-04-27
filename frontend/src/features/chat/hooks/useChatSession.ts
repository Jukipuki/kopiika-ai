"use client";

import { useCallback, useState } from "react";
import { useSession } from "next-auth/react";
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import type { ChatSession } from "../lib/chat-types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface CreateSessionResponse {
  sessionId: string;
  createdAt: string;
  consentVersionAtCreation?: string;
}

interface ListSessionsResponse {
  sessions: ChatSession[];
  nextCursor?: string | null;
}

export interface ChatHistoryMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  guardrailAction: "none" | "blocked" | "modified";
  redactionFlags: Record<string, unknown>;
  createdAt: string;
}

interface ListMessagesResponse {
  messages: ChatHistoryMessage[];
  nextCursor?: string | null;
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

  const sessionsQuery = useQuery<ListSessionsResponse>({
    queryKey: ["chat-sessions"],
    enabled: !!token,
    staleTime: 30_000,
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/v1/chat/sessions`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
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
      qc.invalidateQueries({ queryKey: ["chat-sessions"] });
    },
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: async () => {
      if (!token) throw new Error("not authenticated");
      const res = await fetch(`${API_URL}/api/v1/chat/sessions`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
    },
    onSuccess: () => {
      setActiveSessionId(null);
      qc.invalidateQueries({ queryKey: ["chat-sessions"] });
    },
  });

  const selectSession = useCallback((id: string | null) => setActiveSessionId(id), []);

  return {
    sessions: sessionsQuery.data?.sessions ?? [],
    isLoading: sessionsQuery.isLoading,
    activeSessionId,
    selectSession,
    createSession: createMutation.mutateAsync,
    isCreating: createMutation.isPending,
    createError: createMutation.error as (Error & { status?: number }) | null,
    deleteSession: deleteMutation.mutateAsync,
    isDeleting: deleteMutation.isPending,
    bulkDeleteAll: bulkDeleteMutation.mutateAsync,
    isBulkDeleting: bulkDeleteMutation.isPending,
  };
}

export function useChatMessages(sessionId: string | null) {
  const { data: session } = useSession();
  const token = session?.accessToken;

  return useInfiniteQuery({
    queryKey: ["chat-messages", sessionId],
    enabled: !!token && !!sessionId,
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => {
      const url = new URL(
        `${API_URL}/api/v1/chat/sessions/${sessionId}/messages`,
      );
      if (pageParam) url.searchParams.set("cursor", pageParam);
      const res = await fetch(url.toString(), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return (await res.json()) as ListMessagesResponse;
    },
    getNextPageParam: (last) => last.nextCursor ?? undefined,
  });
}
