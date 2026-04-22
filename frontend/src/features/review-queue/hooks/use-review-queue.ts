"use client";

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ReviewQueueEntry {
  id: string;
  transactionId: string;
  description: string;
  amount: number;
  date: string; // YYYY-MM-DD
  suggestedCategory: string | null;
  suggestedKind: string | null;
  categorizationConfidence: number;
  createdAt: string;
  status: "pending" | "resolved" | "dismissed";
  currencyCode?: number | null;
}

interface ReviewQueuePage {
  items: ReviewQueueEntry[];
  nextCursor: string | null;
  hasMore: boolean;
}

async function fetchPage(
  cursor: string | undefined,
  accessToken: string,
): Promise<ReviewQueuePage> {
  const params = new URLSearchParams({ limit: "25", status: "pending" });
  if (cursor) params.set("cursor", cursor);
  const res = await fetch(
    `${API_URL}/api/v1/transactions/review-queue?${params}`,
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function useReviewQueue() {
  const { data: session } = useSession();
  const accessToken = session?.accessToken;

  const {
    data,
    isLoading,
    isFetchingNextPage,
    error,
    hasNextPage,
    fetchNextPage,
    refetch,
  } = useInfiniteQuery({
    queryKey: ["review-queue", "pending"],
    queryFn: ({ pageParam }) =>
      fetchPage(pageParam as string | undefined, accessToken!),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? (lastPage.nextCursor ?? undefined) : undefined,
    enabled: !!accessToken,
    staleTime: 30 * 1000,
  });

  const items = data?.pages.flatMap((p) => p.items) ?? [];
  return {
    items,
    isLoading,
    isFetchingMore: isFetchingNextPage,
    hasMore: hasNextPage ?? false,
    loadMore: fetchNextPage,
    error: error ? String((error as Error).message) : null,
    refresh: refetch,
  };
}

export class MatrixViolationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MatrixViolationError";
  }
}

export function useResolveQueueEntry() {
  const { data: session } = useSession();
  const qc = useQueryClient();

  return useMutation({
    mutationFn: async ({
      entryId,
      category,
      kind,
    }: {
      entryId: string;
      category: string;
      kind: string;
    }) => {
      const res = await fetch(
        `${API_URL}/api/v1/transactions/review-queue/${entryId}/resolve`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session?.accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ category, kind }),
        },
      );
      if (res.status === 400) {
        throw new MatrixViolationError("kind_category_mismatch");
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["review-queue"] });
      qc.invalidateQueries({ queryKey: ["review-queue-count"] });
    },
  });
}

export function useDismissQueueEntry() {
  const { data: session } = useSession();
  const qc = useQueryClient();

  return useMutation({
    mutationFn: async (entryId: string) => {
      const res = await fetch(
        `${API_URL}/api/v1/transactions/review-queue/${entryId}/dismiss`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session?.accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({}),
        },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["review-queue"] });
      qc.invalidateQueries({ queryKey: ["review-queue-count"] });
    },
  });
}
