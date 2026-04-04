"use client";

import { SkeletonCard } from "./SkeletonCard";

const PHASE_COPY: Record<string, string> = {
  parsing: "Crunching your numbers...",
  categorization: "Finding patterns in your spending...",
  education: "Almost there... crafting your insights",
};

interface ProgressiveLoadingStateProps {
  phase: string | null;
}

export function ProgressiveLoadingState({ phase }: ProgressiveLoadingStateProps) {
  const copy = (phase && PHASE_COPY[phase]) ?? "AI is still thinking...";

  return (
    <div className="flex flex-col gap-4">
      <SkeletonCard />
      <SkeletonCard />
      <p className="animate-pulse text-center text-sm text-muted-foreground">{copy}</p>
    </div>
  );
}
