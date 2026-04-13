"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface UserProfile {
  id: string;
  email: string;
  locale: string;
  isVerified: boolean;
  createdAt: string;
}

interface UseUserProfileReturn {
  profile: UserProfile | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useUserProfile(): UseUserProfileReturn {
  const { data: session } = useSession();
  const accessToken = session?.accessToken;

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["userProfile"],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<UserProfile>;
    },
    enabled: !!accessToken,
  });

  return {
    profile: data ?? null,
    isLoading,
    error: error ? error.message : null,
    refetch,
  };
}
