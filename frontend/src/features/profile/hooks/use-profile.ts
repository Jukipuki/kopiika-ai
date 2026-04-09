"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import type { FinancialProfile } from "../types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useProfile() {
  const { data: session } = useSession();

  const result = useQuery({
    queryKey: ["profile"],
    queryFn: async (): Promise<FinancialProfile> => {
      const res = await fetch(`${API_URL}/api/v1/profile`, {
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      });
      if (res.status === 404) {
        throw new NotFoundError();
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: !!session?.accessToken,
    staleTime: 5 * 60 * 1000,
    retry: (_, error) => !(error instanceof NotFoundError),
  });

  return {
    profile: result.data ?? null,
    isLoading: result.isLoading,
    isError: result.isError,
    isNotFound: result.error instanceof NotFoundError,
  };
}

class NotFoundError extends Error {
  constructor() {
    super("Profile not found");
  }
}
