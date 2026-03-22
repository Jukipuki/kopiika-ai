"use client";

import { useState, useEffect, useCallback, useRef } from "react";
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
  const { data: session, status } = useSession();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchProfile = useCallback(async () => {
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
      const res = await fetch(`${API_URL}/api/v1/auth/me`, {
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
        },
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new Error("Failed to fetch profile");
      }

      const data = await res.json();
      setProfile(data);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError("serverError");
    } finally {
      setIsLoading(false);
    }
  }, [session?.accessToken, status]);

  useEffect(() => {
    fetchProfile();
    return () => {
      abortControllerRef.current?.abort();
    };
  }, [fetchProfile]);

  return { profile, isLoading, error, refetch: fetchProfile };
}
