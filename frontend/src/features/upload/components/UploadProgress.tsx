"use client";

import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";
import ProcessingPipeline from "./ProcessingPipeline";
import type { JobStatusState } from "../types";

interface UploadProgressProps {
  jobStatus?: JobStatusState | null;
  onRetry?: () => void;
  isRetryable?: boolean;
  retryInProgress?: boolean;
}

export default function UploadProgress({ jobStatus, onRetry, isRetryable, retryInProgress }: UploadProgressProps) {
  const t = useTranslations("upload");

  // If no job status yet (still uploading file), show spinner
  if (!jobStatus || jobStatus.status === "idle" || jobStatus.status === "connecting") {
    return (
      <div className="flex flex-col items-center gap-3 py-4">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-sm font-medium text-foreground">
          {t("analyzing")}
        </p>
        <p className="text-xs text-muted-foreground/70">{t("trustMessage")}</p>
      </div>
    );
  }

  // Show pipeline progress once processing starts
  return (
    <div className="flex w-full flex-col items-center gap-3 py-2">
      <ProcessingPipeline
        status={jobStatus.status}
        step={jobStatus.step}
        progress={jobStatus.progress}
        message={jobStatus.message}
        error={jobStatus.error}
        onRetry={onRetry}
        isRetryable={isRetryable ?? jobStatus.isRetryable}
        retryCount={jobStatus.retryCount}
        retryInProgress={retryInProgress}
      />
      {jobStatus.status === "processing" && (
        <p className="text-xs text-muted-foreground/70">{t("trustMessage")}</p>
      )}
    </div>
  );
}
