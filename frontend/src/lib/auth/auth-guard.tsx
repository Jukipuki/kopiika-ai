"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { useAuth } from "@/features/auth/hooks/use-auth";

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-foreground/10 ${className ?? ""}`}
    />
  );
}

function DashboardSkeleton() {
  const t = useTranslations("common");

  return (
    <div className="min-h-screen bg-background" aria-label={t("loading")}>
      <div className="border-b border-foreground/10">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <Skeleton className="h-7 w-28" />
          <Skeleton className="h-8 w-20 rounded-lg" />
        </div>
      </div>
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <Skeleton className="mb-6 h-8 w-48" />
        <div className="space-y-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-3/4" />
        </div>
      </main>
    </div>
  );
}

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const locale = useLocale();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      const callbackUrl = encodeURIComponent(pathname);
      router.replace(`/${locale}/login?callbackUrl=${callbackUrl}`);
    }
  }, [isAuthenticated, isLoading, router, pathname, locale]);

  if (isLoading) {
    return <DashboardSkeleton />;
  }

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
