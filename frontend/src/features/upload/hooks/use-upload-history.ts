"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface UploadHistoryItem {
  id: string;
  fileName: string;
  detectedFormat: string | null;
  createdAt: string;
  transactionCount: number;
  duplicatesSkipped: number;
  status: string;
}

interface UploadHistoryPage {
  items: UploadHistoryItem[];
  total: number;
  nextCursor: string | null;
  hasMore: boolean;
}

async function fetchUploadsPage(
  cursor: string | undefined,
  accessToken: string,
): Promise<UploadHistoryPage> {
  const params = new URLSearchParams({ pageSize: "20" });
  if (cursor) params.set("cursor", cursor);

  const res = await fetch(`${API_URL}/api/v1/uploads?${params}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

interface UseUploadHistoryReturn {
  uploads: UploadHistoryItem[];
  total: number;
  isLoading: boolean;
  isFetchingMore: boolean;
  error: string | null;
  hasMore: boolean;
  loadMore: () => void;
  refresh: () => void;
}

export function useUploadHistory(): UseUploadHistoryReturn {
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
    queryKey: ["uploads"],
    queryFn: ({ pageParam }) =>
      fetchUploadsPage(pageParam as string | undefined, accessToken!),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? (lastPage.nextCursor ?? undefined) : undefined,
    enabled: !!accessToken,
    staleTime: 30 * 1000, // 30 seconds
  });

  const uploads = data?.pages.flatMap((page) => page.items) ?? [];
  const total = data?.pages[0]?.total ?? 0;

  return {
    uploads,
    total,
    isLoading,
    isFetchingMore: isFetchingNextPage,
    error: error ? error.message : null,
    hasMore: hasNextPage ?? false,
    loadMore: fetchNextPage,
    refresh: refetch,
  };
}
