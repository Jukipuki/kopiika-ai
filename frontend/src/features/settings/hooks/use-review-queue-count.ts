"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface CountResponse {
  count: number;
}

export function useReviewQueueCount() {
  const { data: session } = useSession();
  const accessToken = session?.accessToken;

  const { data, isLoading, error } = useQuery({
    queryKey: ["review-queue-count"],
    queryFn: async (): Promise<CountResponse> => {
      const res = await fetch(
        `${API_URL}/api/v1/transactions/review-queue/count`,
        { headers: { Authorization: `Bearer ${accessToken}` } },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: !!accessToken,
    staleTime: 60 * 1000,
  });

  return {
    count: data?.count ?? 0,
    isLoading,
    isError: !!error,
  };
}
