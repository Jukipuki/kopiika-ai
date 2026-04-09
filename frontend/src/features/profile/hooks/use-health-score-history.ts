"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import type { HealthScoreHistory } from "../types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useHealthScoreHistory() {
  const { data: session } = useSession();

  const result = useQuery({
    queryKey: ["health-score-history"],
    queryFn: async (): Promise<HealthScoreHistory> => {
      const res = await fetch(`${API_URL}/api/v1/health-score/history`, {
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: !!session?.accessToken,
    staleTime: 5 * 60 * 1000,
  });

  return {
    history: result.data ?? [],
    isLoading: result.isLoading,
    isError: result.isError,
  };
}
