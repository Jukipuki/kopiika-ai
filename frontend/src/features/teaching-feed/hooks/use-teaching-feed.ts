"use client";

import { useMemo } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import type { InsightCard, InsightListResponse } from "../types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useTeachingFeed() {
  const { data: session } = useSession();

  const result = useInfiniteQuery({
    queryKey: ["teaching-feed"],
    queryFn: async ({ pageParam }: { pageParam: string | undefined }): Promise<InsightListResponse> => {
      const url = new URL(`${API_URL}/api/v1/insights`);
      url.searchParams.set("pageSize", "20");
      if (pageParam) url.searchParams.set("cursor", pageParam);
      const res = await fetch(url.toString(), {
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.hasMore ? lastPage.nextCursor ?? undefined : undefined,
    enabled: !!session?.accessToken,
    staleTime: 5 * 60 * 1000,
  });

  // Flatten + deduplicate by ID across pages
  const cards = useMemo(() => {
    const seen = new Set<string>();
    const deduped: InsightCard[] = [];
    for (const page of result.data?.pages ?? []) {
      for (const card of page.items) {
        if (!seen.has(card.id)) {
          seen.add(card.id);
          deduped.push(card);
        }
      }
    }
    return deduped;
  }, [result.data?.pages]);

  return {
    cards,
    fetchNextPage: result.fetchNextPage,
    hasNextPage: result.hasNextPage,
    isFetchingNextPage: result.isFetchingNextPage,
    isFetchNextPageError: result.isError && cards.length > 0,
    isLoading: result.isLoading,
    isError: result.isError,
    isFetching: result.isFetching,
  };
}
