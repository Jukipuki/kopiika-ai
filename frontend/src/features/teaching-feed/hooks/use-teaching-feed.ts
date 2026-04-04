"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import type { InsightCard, InsightListResponse } from "../types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useTeachingFeed() {
  const { data: session } = useSession();

  return useQuery({
    queryKey: ["teaching-feed"],
    queryFn: async (): Promise<InsightCard[]> => {
      const res = await fetch(`${API_URL}/api/v1/insights`, {
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: InsightListResponse = await res.json();
      return data.items;
    },
    enabled: !!session?.accessToken,
    staleTime: 5 * 60 * 1000,
  });
}
