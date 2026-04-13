"use client";

import { useState, useCallback } from "react";
import { useSession } from "next-auth/react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface UseRetryJobReturn {
  retryJob: (jobId: string) => Promise<boolean>;
  isRetrying: boolean;
  error: string | null;
}

export function useRetryJob(): UseRetryJobReturn {
  const { data: session } = useSession();
  const [isRetrying, setIsRetrying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const retryJob = useCallback(
    async (jobId: string): Promise<boolean> => {
      if (!session?.accessToken) {
        setError("UNAUTHENTICATED");
        return false;
      }

      setIsRetrying(true);
      setError(null);

      try {
        const res = await fetch(`${API_URL}/api/v1/jobs/${jobId}/retry`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session.accessToken}`,
          },
        });

        if (!res.ok) {
          const data = await res.json();
          const serverError = data.error || { code: "RETRY_FAILED", message: "Retry failed" };
          throw new Error(`${res.status}: ${serverError.code}`);
        }

        return true;
      } catch (err) {
        const message = err instanceof Error ? err.message : "RETRY_FAILED";
        setError(message);
        return false;
      } finally {
        setIsRetrying(false);
      }
    },
    [session?.accessToken],
  );

  return { retryJob, isRetrying, error };
}
