"use client";

import { useMutation } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface UseAccountDeletionReturn {
  deleteAccount: () => Promise<boolean>;
  isDeleting: boolean;
  error: string | null;
}

export function useAccountDeletion(): UseAccountDeletionReturn {
  const { data: session } = useSession();

  const mutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_URL}/api/v1/users/me`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    },
  });

  const deleteAccount = async (): Promise<boolean> => {
    try {
      await mutation.mutateAsync();
      return true;
    } catch {
      return false;
    }
  };

  return {
    deleteAccount,
    isDeleting: mutation.isPending,
    error: mutation.error ? mutation.error.message : null,
  };
}
