"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface TransactionDateRange {
  earliest: string;
  latest: string;
}

export interface FinancialProfileSummary {
  totalIncome: number;
  totalExpenses: number;
  categoryTotals: Record<string, number>;
}

export interface HealthScoreEntry {
  score: number;
  calculatedAt: string;
}

export interface ConsentRecord {
  consentType: string;
  grantedAt: string;
}

export interface FeedbackVoteCounts {
  up: number;
  down: number;
}

export interface FreeTextFeedbackEntry {
  cardId: string;
  freeText: string;
  feedbackSource: string;
  createdAt: string;
}

export interface FeedbackSummary {
  voteCounts: FeedbackVoteCounts;
  issueReportCount: number;
  freeTextEntries: FreeTextFeedbackEntry[];
  feedbackResponses: Array<Record<string, unknown>>;
}

export interface DataSummary {
  uploadCount: number;
  transactionCount: number;
  transactionDateRange: TransactionDateRange | null;
  categoriesDetected: string[];
  insightCount: number;
  financialProfile: FinancialProfileSummary | null;
  healthScoreHistory: HealthScoreEntry[];
  consentRecords: ConsentRecord[];
  feedbackSummary: FeedbackSummary;
}

interface UseDataSummaryReturn {
  data: DataSummary | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useDataSummary(): UseDataSummaryReturn {
  const { data: session } = useSession();
  const accessToken = session?.accessToken;

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["dataSummary"],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/v1/users/me/data-summary`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<DataSummary>;
    },
    enabled: !!accessToken,
  });

  return {
    data: data ?? null,
    isLoading,
    error: error ? error.message : null,
    refetch,
  };
}
