"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

export type MilestoneCardType =
  | "milestone_3rd_upload"
  | "health_score_change";

export type MilestoneVariant = "emoji_rating" | "yes_no";

export interface MilestoneFeedbackCardOut {
  cardType: MilestoneCardType;
  variant: MilestoneVariant;
}

interface PendingMilestoneCardsResponse {
  cards: MilestoneFeedbackCardOut[];
}

interface SubmitArgs {
  cardType: MilestoneCardType;
  responseValue: string;
  freeText?: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const QUERY_KEY = ["milestone-feedback", "pending"] as const;

// Module-level flag persists for the browser tab's lifetime. Once a card has
// been shown (responded OR dismissed) in this session, suppress further ones
// until a full reload. Exposed as an object so tests can reset it.
export const _milestoneSession = { hasShownCard: false };

export function useMilestoneFeedback() {
  const { data: session } = useSession();
  const queryClient = useQueryClient();
  const token = session?.accessToken;

  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: async (): Promise<PendingMilestoneCardsResponse> => {
      const res = await fetch(
        `${API_URL}/api/v1/milestone-feedback/pending`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<PendingMilestoneCardsResponse>;
    },
    enabled: !!token,
    staleTime: 0,
  });

  const rawCard = query.data?.cards?.[0] ?? null;
  const pendingCard = _milestoneSession.hasShownCard ? null : rawCard;

  const mutation = useMutation({
    mutationFn: async ({ cardType, responseValue, freeText }: SubmitArgs) => {
      const res = await fetch(
        `${API_URL}/api/v1/milestone-feedback/respond`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            cardType,
            responseValue,
            ...(freeText !== undefined ? { freeText } : {}),
          }),
        },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<{ ok: boolean }>;
    },
    onSuccess: () => {
      _milestoneSession.hasShownCard = true;
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });

  return {
    pendingCard,
    submitResponse: mutation.mutate,
    isPending: mutation.isPending,
  };
}
