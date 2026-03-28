"use client";

import { useTranslations } from "next-intl";
import { CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { JobStatusState } from "../types";

const STAGES = [
  "readingTransactions",
  "categorizingSpending",
  "detectingPatterns",
  "scoringHealth",
  "generatingInsights",
] as const;

// Map backend step values to frontend stage indices
function getActiveStageIndex(step: string | null, progress: number): number {
  if (!step) return 0;
  if (step === "ingestion" && progress <= 10) return 0;
  if (step === "ingestion" && progress <= 30) return 0;
  // Future Epic 3 stages
  if (step === "categorization") return 1;
  if (step === "patterns") return 2;
  if (step === "scoring") return 3;
  if (step === "insights") return 4;
  if (step === "done") return STAGES.length;
  // Default: map progress percentage to stages
  if (progress >= 100) return STAGES.length;
  if (progress >= 80) return 4;
  if (progress >= 60) return 3;
  if (progress >= 40) return 2;
  if (progress >= 30) return 1;
  return 0;
}

interface ProcessingPipelineProps {
  status: JobStatusState["status"];
  step: string | null;
  progress: number;
  error: JobStatusState["error"];
  onRetry?: () => void;
}

export default function ProcessingPipeline({
  status,
  step,
  progress,
  error,
  onRetry,
}: ProcessingPipelineProps) {
  const t = useTranslations("upload.processing");

  const isCompleted = status === "completed";
  const isFailed = status === "failed";
  const isProcessing = status === "processing" || status === "connecting";

  const activeIndex = isCompleted
    ? STAGES.length
    : isFailed
      ? -1
      : getActiveStageIndex(step, progress);

  return (
    <div
      role="progressbar"
      aria-valuenow={isCompleted ? STAGES.length : activeIndex + 1}
      aria-valuemin={1}
      aria-valuemax={STAGES.length}
      aria-label={t("ariaLabel")}
      className="flex w-full flex-col gap-1 py-2"
    >
      <ol className="flex flex-col gap-3" aria-live="polite">
        {STAGES.map((stageKey, index) => {
          const isActive = isProcessing && index === activeIndex;
          const isDone = isCompleted || index < activeIndex;
          const isPending = !isDone && !isActive;

          return (
            <li key={stageKey} className="flex items-start gap-3">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center">
                {isDone && (
                  <CheckCircle2 className="h-5 w-5 text-green-500" aria-hidden="true" />
                )}
                {isActive && (
                  <Loader2
                    className="h-5 w-5 text-primary motion-safe:animate-spin"
                    aria-hidden="true"
                  />
                )}
                {isPending && (
                  <span className="h-2 w-2 rounded-full bg-muted-foreground/30" aria-hidden="true" />
                )}
              </span>
              <div className="flex flex-col">
                <span
                  className={`text-sm leading-tight ${
                    isDone
                      ? "text-muted-foreground"
                      : isActive
                        ? "font-medium text-foreground"
                        : "text-muted-foreground/50"
                  }`}
                >
                  {t(`stages.${stageKey}`)}
                </span>
                {isActive && (
                  <span className="mt-0.5 text-xs text-muted-foreground motion-safe:animate-pulse">
                    {t(`education.${stageKey}`)}
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {isFailed && (
        <div className="mt-4 flex flex-col items-center gap-3 rounded-lg border border-destructive/20 bg-destructive/5 p-4 text-center">
          <AlertCircle className="h-8 w-8 text-destructive" />
          <p className="text-sm text-destructive">{t("errorMessage")}</p>
          {onRetry && (
            <Button
              variant="outline"
              size="sm"
              onClick={onRetry}
              className="min-h-[44px] min-w-[44px]"
            >
              {t("retry")}
            </Button>
          )}
        </div>
      )}

      {isCompleted && (
        <div className="mt-4 flex flex-col items-center gap-2 text-center">
          <CheckCircle2 className="h-8 w-8 text-green-500" />
          <p className="text-sm font-medium text-foreground">{t("complete")}</p>
        </div>
      )}
    </div>
  );
}
