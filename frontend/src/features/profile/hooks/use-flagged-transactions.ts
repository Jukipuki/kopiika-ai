"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type UncategorizedReason =
  | "low_confidence"
  | "parse_failure"
  | "llm_unavailable"
  | "currency_unknown";

export interface FlaggedTransaction {
  id: string;
  uploadId: string;
  date: string;
  description: string;
  amount: number;
  uncategorizedReason: UncategorizedReason | null;
  currencyUnknownRaw?: string | null;
}

class NotFoundError extends Error {
  constructor() {
    super("Not found");
  }
}

export function useFlaggedTransactions() {
  const { data: session } = useSession();

  const result = useQuery({
    queryKey: ["flagged-transactions"],
    queryFn: async (): Promise<FlaggedTransaction[]> => {
      const res = await fetch(`${API_URL}/api/v1/transactions/flagged`, {
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      });
      if (res.status === 404) throw new NotFoundError();
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: !!session?.accessToken,
    staleTime: 5 * 60 * 1000,
    retry: (_, error) => !(error instanceof NotFoundError),
  });

  return {
    flaggedTransactions: result.data ?? [],
    isLoading: result.isLoading,
    isError: result.isError,
  };
}
