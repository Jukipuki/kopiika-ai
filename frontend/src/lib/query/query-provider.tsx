"use client";

import {
  QueryClient,
  QueryClientProvider,
  QueryCache,
  MutationCache,
} from "@tanstack/react-query";
import { useRef } from "react";
import { signOut } from "next-auth/react";
import { useLocale, useTranslations } from "next-intl";
import { toast } from "sonner";

function getStatusFromError(error: unknown): number | undefined {
  if (
    error &&
    typeof error === "object" &&
    "status" in error &&
    typeof (error as { status: unknown }).status === "number"
  ) {
    return (error as { status: number }).status;
  }
  // Parse "HTTP 4xx" / "HTTP 5xx" from error messages (existing convention)
  if (error instanceof Error) {
    const match = error.message.match(/^HTTP (\d{3})$/);
    if (match) return parseInt(match[1], 10);
  }
  return undefined;
}

export default function QueryProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = useLocale();
  const t = useTranslations("errors");

  const tRef = useRef(t);
  tRef.current = t;
  const localeRef = useRef(locale);
  localeRef.current = locale;

  const queryClientRef = useRef<QueryClient | null>(null);
  if (!queryClientRef.current) {
    const handleError = (error: unknown) => {
      const status = getStatusFromError(error);

      if (status === 401) {
        signOut({ callbackUrl: `/${localeRef.current}/login` });
        return;
      }

      if (status === 429) {
        toast.error(tRef.current("rateLimitToast"));
        return;
      }

      if (status && status >= 500) {
        toast.error(tRef.current("generic"));
      }
    };

    queryClientRef.current = new QueryClient({
      queryCache: new QueryCache({ onError: handleError }),
      mutationCache: new MutationCache({ onError: handleError }),
      defaultOptions: {
        queries: {
          staleTime: 60 * 1000,
          retry: 1,
        },
      },
    });
  }

  return (
    <QueryClientProvider client={queryClientRef.current}>
      {children}
    </QueryClientProvider>
  );
}
