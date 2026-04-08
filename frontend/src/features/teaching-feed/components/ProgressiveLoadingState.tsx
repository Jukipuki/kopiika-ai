"use client";

import { useTranslations } from "next-intl";
import { SkeletonCard } from "./SkeletonCard";

interface ProgressiveLoadingStateProps {
  message: string | null;
}

export function ProgressiveLoadingState({ message }: ProgressiveLoadingStateProps) {
  const t = useTranslations("feed");
  return (
    <div className="flex flex-col gap-4">
      <SkeletonCard />
      <SkeletonCard />
      <p className="animate-pulse text-center text-sm text-muted-foreground">{message ?? t("processing")}</p>
    </div>
  );
}
