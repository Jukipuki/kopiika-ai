"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

export type VoteValue = "up" | "down";

export interface CardFeedbackState {
  vote: VoteValue | null;
  reasonChip: string | null;
  createdAt: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useCardFeedback(cardId: string) {
  const { data: session } = useSession();
  const queryClient = useQueryClient();
  const token = session?.accessToken;
  const queryKey = ["card-feedback", cardId];

  const { data } = useQuery({
    queryKey,
    queryFn: async (): Promise<CardFeedbackState | null> => {
      const res = await fetch(
        `${API_URL}/api/v1/feedback/cards/${cardId}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<CardFeedbackState>;
    },
    enabled: !!token && !!cardId,
    staleTime: 5 * 60 * 1000,
  });

  const mutation = useMutation({
    mutationFn: async (vote: VoteValue) => {
      const res = await fetch(
        `${API_URL}/api/v1/feedback/cards/${cardId}/vote`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ vote }),
        },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onMutate: async (newVote) => {
      await queryClient.cancelQueries({ queryKey });
      const previous =
        queryClient.getQueryData<CardFeedbackState | null>(queryKey);
      queryClient.setQueryData(
        queryKey,
        (old: CardFeedbackState | null | undefined) =>
          old
            ? { ...old, vote: newVote }
            : {
                vote: newVote,
                reasonChip: null,
                createdAt: new Date().toISOString(),
              },
      );
      return { previous };
    },
    onError: (_err, _vote, context) => {
      queryClient.setQueryData(queryKey, context?.previous);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  return {
    vote: (data?.vote ?? null) as VoteValue | null,
    submitVote: mutation.mutate,
    isPending: mutation.isPending,
  };
}
