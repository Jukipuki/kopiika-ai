"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useLocale } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { CONSENT_TYPE_AI_PROCESSING } from "@/features/onboarding/consent-version";
import DashboardSkeleton from "@/components/layout/DashboardSkeleton";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ConsentStatus {
  hasCurrentConsent: boolean;
  version: string;
  grantedAt: string | null;
  locale: string | null;
}

export default function ConsentGuard({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: session, status: sessionStatus } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const locale = useLocale();

  const isOnOnboardingRoute = pathname?.startsWith(`/${locale}/onboarding`);

  const {
    data: consent,
    isLoading,
    isFetching,
    isError,
  } = useQuery<ConsentStatus>({
    queryKey: ["consent", CONSENT_TYPE_AI_PROCESSING],
    enabled: !!session?.accessToken && !isOnOnboardingRoute,
    staleTime: Infinity,
    queryFn: async () => {
      const res = await fetch(
        `${API_URL}/api/v1/users/me/consent?type=${CONSENT_TYPE_AI_PROCESSING}`,
        {
          headers: {
            Authorization: `Bearer ${session?.accessToken}`,
          },
        },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return (await res.json()) as ConsentStatus;
    },
  });

  useEffect(() => {
    if (isOnOnboardingRoute) return;
    if (sessionStatus !== "authenticated") return;
    if (isLoading || isFetching) return;
    // Fail-closed: if the consent check errors out, redirect to onboarding
    // rather than silently letting an unconsented user through.
    if (isError || (consent && consent.hasCurrentConsent === false)) {
      router.replace(`/${locale}/onboarding/privacy`);
    }
  }, [
    isOnOnboardingRoute,
    sessionStatus,
    isLoading,
    isFetching,
    isError,
    consent,
    router,
    locale,
  ]);

  // Onboarding routes do not need the consent check — short-circuit.
  if (isOnOnboardingRoute) {
    return <>{children}</>;
  }

  if (sessionStatus === "loading" || isLoading) {
    return <DashboardSkeleton />;
  }

  if (isError || (consent && consent.hasCurrentConsent === false)) {
    // Redirect is pending — render nothing to avoid flashing dashboard chrome.
    return null;
  }

  return <>{children}</>;
}
