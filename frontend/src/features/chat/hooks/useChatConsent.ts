"use client";

import { useCallback } from "react";
import { useSession } from "next-auth/react";
import { useLocale } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  CONSENT_TYPE_CHAT_PROCESSING,
  CURRENT_CHAT_CONSENT_VERSION,
} from "@/features/onboarding/consent-version";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const CHAT_PROCESSING = CONSENT_TYPE_CHAT_PROCESSING;

export interface ChatConsentStatus {
  hasCurrentConsent: boolean;
  version: string;
  grantedAt: string | null;
  locale: string | null;
}

export function useChatConsent() {
  const { data: session } = useSession();
  const token = session?.accessToken;
  const locale = useLocale();
  const qc = useQueryClient();

  const query = useQuery<ChatConsentStatus>({
    queryKey: ["consent", CHAT_PROCESSING],
    enabled: !!token,
    refetchOnWindowFocus: true,
    queryFn: async () => {
      const res = await fetch(
        `${API_URL}/api/v1/users/me/consent?type=${CHAT_PROCESSING}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return (await res.json()) as ChatConsentStatus;
    },
  });

  const grantMutation = useMutation({
    mutationFn: async () => {
      if (!token) throw new Error("not authenticated");
      const res = await fetch(`${API_URL}/api/v1/users/me/consent`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          version: CURRENT_CHAT_CONSENT_VERSION,
          locale,
          consentType: CHAT_PROCESSING,
        }),
      });
      if (!res.ok) {
        // Surface the backend's structured error message (e.g.
        // CONSENT_VERSION_MISMATCH) instead of a bare "HTTP 422" so the
        // dialog can render something useful. Mirrors the pattern in
        // PrivacyExplanationScreen.
        const errorData = (await res.json().catch(() => null)) as
          | { error?: { message?: string } }
          | null;
        throw new Error(
          errorData?.error?.message ?? `HTTP ${res.status}`,
        );
      }
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["consent", CHAT_PROCESSING] });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: async () => {
      if (!token) throw new Error("not authenticated");
      const res = await fetch(
        `${API_URL}/api/v1/users/me/consent?type=${CHAT_PROCESSING}`,
        { method: "DELETE", headers: { Authorization: `Bearer ${token}` } },
      );
      if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["consent", CHAT_PROCESSING] });
    },
  });

  const grant = useCallback(() => grantMutation.mutateAsync(), [grantMutation]);
  const revoke = useCallback(() => revokeMutation.mutateAsync(), [revokeMutation]);

  return {
    isLoading: query.isLoading,
    consent: query.data,
    hasCurrentConsent: query.data?.hasCurrentConsent ?? false,
    grant,
    isGranting: grantMutation.isPending,
    revoke,
    isRevoking: revokeMutation.isPending,
  };
}
