"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface UseAccountDeletionReturn {
  deleteAccount: () => Promise<boolean>;
  isDeleting: boolean;
  error: string | null;
}

export function useAccountDeletion(): UseAccountDeletionReturn {
  const { data: session } = useSession();
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const deleteAccount = async (): Promise<boolean> => {
    if (!session?.accessToken) {
      setError("unauthenticated");
      return false;
    }

    setIsDeleting(true);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/v1/users/me`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
        },
      });

      if (!res.ok) {
        throw new Error("Failed to delete account");
      }

      return true;
    } catch {
      setError("deleteFailed");
      return false;
    } finally {
      setIsDeleting(false);
    }
  };

  return { deleteAccount, isDeleting, error };
}
