"use client";

import { useState, useEffect, useCallback, useRef } from "react";
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

export interface DataSummary {
  uploadCount: number;
  transactionCount: number;
  transactionDateRange: TransactionDateRange | null;
  categoriesDetected: string[];
  insightCount: number;
  financialProfile: FinancialProfileSummary | null;
  healthScoreHistory: HealthScoreEntry[];
  consentRecords: ConsentRecord[];
}

interface UseDataSummaryReturn {
  data: DataSummary | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useDataSummary(): UseDataSummaryReturn {
  const { data: session, status } = useSession();
  const [data, setData] = useState<DataSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchSummary = useCallback(async () => {
    if (!session?.accessToken) {
      if (status !== "loading") {
        setIsLoading(false);
      }
      return;
    }

    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/v1/users/me/data-summary`, {
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
        },
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new Error("Failed to fetch data summary");
      }

      const json = await res.json();
      setData(json);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError("serverError");
    } finally {
      setIsLoading(false);
    }
  }, [session?.accessToken, status]);

  useEffect(() => {
    fetchSummary();
    return () => {
      abortControllerRef.current?.abort();
    };
  }, [fetchSummary]);

  return { data, isLoading, error, refetch: fetchSummary };
}
