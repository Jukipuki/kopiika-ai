"use client";

import { useSession } from "next-auth/react";

export function useAuth() {
  const { data: session, status } = useSession();

  const hasRefreshError = session?.error === "TokenRefreshFailed";

  return {
    user: session?.user ?? null,
    isAuthenticated: status === "authenticated" && !hasRefreshError,
    isLoading: status === "loading",
  };
}
