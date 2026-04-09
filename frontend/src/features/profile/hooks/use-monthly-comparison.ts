"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import type { MonthlyComparison } from "../types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useMonthlyComparison() {
  const { data: session } = useSession();

  const result = useQuery({
    queryKey: ["monthly-comparison"],
    queryFn: async (): Promise<MonthlyComparison | null> => {
      const res = await fetch(`${API_URL}/api/v1/profile/monthly-comparison`, {
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const text = await res.text();
      if (!text || text === "null") return null;
      return JSON.parse(text);
    },
    enabled: !!session?.accessToken,
    staleTime: 5 * 60 * 1000,
  });

  return {
    comparison: result.data ?? null,
    isLoading: result.isLoading,
    isError: result.isError,
  };
}
