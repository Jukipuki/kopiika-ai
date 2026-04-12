"use client";

import { useTranslations } from "next-intl";

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-foreground/10 ${className ?? ""}`}
    />
  );
}

export default function DashboardSkeleton() {
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
