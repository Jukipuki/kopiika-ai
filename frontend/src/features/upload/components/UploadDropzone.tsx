"use client";

import { useState, useCallback, useRef } from "react";
import { useTranslations } from "next-intl";
import { Upload, FileUp, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useUpload } from "../hooks/use-upload";
import { useJobStatus } from "../hooks/use-job-status";
import { useRetryJob } from "../hooks/use-retry-job";
import UploadProgress from "./UploadProgress";
import UploadSummaryCard from "./UploadSummaryCard";
import FileFormatGuide from "./FileFormatGuide";
import type { UploadState, UploadResponse } from "../types";

const ALLOWED_EXTENSIONS = [".csv", ".pdf"];
const ACCEPT = ".csv,.pdf,text/csv,application/pdf";

const ERROR_KEY_MAP: Record<string, string> = {
  INVALID_FILE_TYPE: "errorInvalidFileType",
  FILE_TOO_LARGE: "errorFileTooLarge",
  RATE_LIMITED: "errorRateLimited",
  UPLOAD_FAILED: "errorUploadFailed",
  INVALID_FILE_STRUCTURE: "errorInvalidFileStructure",
  UNSUPPORTED_BANK_FORMAT: "errorUnsupportedBankFormat",
  ENCODING_ERROR: "errorEncodingError",
  EMPTY_FILE: "errorEmptyFile",
  CORRUPTED_FILE: "errorCorruptedFile",
  UNAUTHENTICATED: "errorUnauthenticated",
};

const ERROR_SUGGESTION_MAP: Record<string, string[]> = {
  INVALID_FILE_TYPE: ["suggestionExportCsv"],
  FILE_TOO_LARGE: [],
  INVALID_FILE_STRUCTURE: ["suggestionCheckCsv", "suggestionReExport"],
  UNSUPPORTED_BANK_FORMAT: ["suggestionSupportMonobank", "suggestionTryMonobank", "suggestionOtherBanksSoon"],
  ENCODING_ERROR: ["suggestionReExportFile", "suggestionNotCorrupted"],
  EMPTY_FILE: ["suggestionCheckTransactionData", "suggestionDownloadAgain"],
  CORRUPTED_FILE: ["suggestionDownloadFromBank"],
  RATE_LIMITED: ["suggestionWaitAndRetry"],
};

const FORMAT_LABEL_MAP: Record<string, string> = {
  monobank: "formatDetectedMonobank",
  privatbank: "formatDetectedPrivatbank",
  unknown: "formatDetectedUnknown",
};

export default function UploadDropzone() {
  const t = useTranslations("upload");
  const { upload, isUploading, error, clearError } = useUpload();
  const { retryJob, isRetrying } = useRetryJob();
  const [dragState, setDragState] = useState<UploadState>("idle");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [lastUploadResult, setLastUploadResult] = useState<UploadResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounterRef = useRef(0);

  const jobStatus = useJobStatus(activeJobId);

  const isProcessing = activeJobId !== null && jobStatus.status !== "completed" && jobStatus.status !== "failed" && jobStatus.status !== "idle";
  const processingComplete = jobStatus.status === "completed";
  const processingFailed = jobStatus.status === "failed";

  const handleUploadAnother = useCallback(() => {
    setActiveJobId(null);
    setSelectedFile(null);
    setLastUploadResult(null);
    clearError();
  }, [clearError]);

  const getState = (): UploadState => {
    if (error) return "error";
    if (isUploading || isProcessing) return "uploading";
    if (dragState === "drag-over") return "drag-over";
    if (selectedFile) return "selected";
    return "idle";
  };

  const handleFile = useCallback(
    async (file: File) => {
      clearError();
      setSelectedFile(file);
      setActiveJobId(null);
      setLastUploadResult(null);

      const result = await upload(file);
      if (result) {
        setLastUploadResult(result);
        setActiveJobId(result.jobId);
      }
    },
    [upload, clearError],
  );

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current++;
    setDragState("drag-over");
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) {
      setDragState("idle");
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounterRef.current = 0;
      setDragState("idle");

      const file = e.dataTransfer.files[0];
      if (file) {
        handleFile(file);
      }
    },
    [handleFile],
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        handleFile(file);
      }
      // Reset input so same file can be re-selected
      e.target.value = "";
    },
    [handleFile],
  );

  const handleClick = useCallback(() => {
    if (!isUploading && !isProcessing) {
      fileInputRef.current?.click();
    }
  }, [isUploading, isProcessing]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleClick();
      }
    },
    [handleClick],
  );

  const state = getState();

  const errorKey = error ? (ERROR_KEY_MAP[error.code] || "errorUploadFailed") : null;
  const errorMessage = errorKey ? t(errorKey) : null;

  // Use i18n keys for suggestions based on error code (not raw server strings)
  const suggestionKeys = error ? (ERROR_SUGGESTION_MAP[error.code] || []) : [];

  // Format detection fallback when backend doesn't supply bankName (unknown formats)
  const formatFallbackKey = lastUploadResult?.detectedFormat
    ? FORMAT_LABEL_MAP[lastUploadResult.detectedFormat] ?? null
    : null;
  const formatFallbackLabel = formatFallbackKey ? t(formatFallbackKey) : null;

  return (
    <Card className="mx-auto w-full max-w-[600px]">
      <CardContent className="p-6">
        <div
          role="button"
          tabIndex={0}
          aria-label={t("dropzoneLabel")}
          onClick={handleClick}
          onKeyDown={handleKeyDown}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className={`
            flex min-h-[200px] cursor-pointer flex-col items-center justify-center gap-4 rounded-lg border-2 border-dashed p-8 transition-all duration-150
            ${state === "idle" ? "border-foreground/20 hover:border-primary/50 hover:bg-primary/5" : ""}
            ${state === "drag-over" ? "border-primary bg-primary/10" : ""}
            ${state === "selected" || state === "uploading" ? "border-primary/30 bg-primary/5" : ""}
            ${state === "error" ? "border-destructive/50 bg-destructive/5" : ""}
          `}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPT}
            onChange={handleFileSelect}
            className="hidden"
            aria-hidden="true"
          />

          {state === "uploading" && (
            <UploadProgress
              jobStatus={activeJobId ? jobStatus : null}
              isRetryable={jobStatus.isRetryable}
              retryInProgress={isRetrying}
              onRetry={activeJobId ? async () => {
                const success = await retryJob(activeJobId);
                if (!success) {
                  setActiveJobId(null);
                  setSelectedFile(null);
                }
              } : undefined}
            />
          )}

          {state === "error" && (
            <div className="flex flex-col items-center gap-3 text-center">
              <AlertCircle className="h-10 w-10 text-destructive" />
              <p className="text-sm text-destructive">{errorMessage}</p>
              {suggestionKeys.length > 0 && (
                <ul className="flex flex-col gap-1 text-xs text-muted-foreground" role="list" aria-label="Suggestions">
                  {suggestionKeys.map((key) => (
                    <li key={key}>{t(key)}</li>
                  ))}
                </ul>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  clearError();
                  setSelectedFile(null);
                  setActiveJobId(null);
                }}
                className="min-h-[44px] min-w-[44px]"
              >
                {t("tryAgain")}
              </Button>
            </div>
          )}

          {processingFailed && state !== "uploading" && (
            <div className="flex flex-col items-center gap-3 text-center">
              <AlertCircle className="h-10 w-10 text-destructive" />
              <p className="text-sm text-destructive">{t("processing.errorMessage")}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveJobId(null);
                  setSelectedFile(null);
                }}
                className="min-h-[44px] min-w-[44px]"
              >
                {t("tryAgain")}
              </Button>
            </div>
          )}

          {processingComplete && jobStatus.result && (
            <div
              className="w-full"
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => e.stopPropagation()}
              role="presentation"
            >
              <UploadSummaryCard
                bankName={jobStatus.result.bankName ?? null}
                transactionCount={jobStatus.result.transactionCount ?? jobStatus.result.newTransactions ?? 0}
                dateRange={jobStatus.result.dateRange ?? null}
                totalInsights={jobStatus.result.totalInsights}
                duplicatesSkipped={jobStatus.result.duplicatesSkipped ?? 0}
                newTransactions={jobStatus.result.newTransactions ?? 0}
                fallbackBankLabel={formatFallbackLabel}
                rejectedRows={jobStatus.result.rejectedRows}
                warnings={jobStatus.result.warnings}
                onUploadAnother={handleUploadAnother}
              />
            </div>
          )}

          {state === "selected" && !isUploading && !processingComplete && !processingFailed && (
            <div className="flex flex-col items-center gap-3 text-center">
              <FileUp className="h-10 w-10 text-primary" />
              <div>
                <p className="text-sm font-medium text-foreground">
                  {selectedFile?.name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {selectedFile && formatFileSize(selectedFile.size)}
                </p>
              </div>
            </div>
          )}

          {(state === "idle" || state === "drag-over") && (
            <div className="flex flex-col items-center gap-3 text-center">
              <Upload
                className={`h-10 w-10 transition-transform duration-150 ${
                  state === "drag-over"
                    ? "scale-110 text-primary"
                    : "text-muted-foreground"
                }`}
              />
              <div>
                <p className="text-sm font-medium text-foreground">
                  {t("dropHere")}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {t("orClickToSelect")}
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="mt-4 flex flex-col items-center gap-2">
          <FileFormatGuide />
          <p className="text-xs text-muted-foreground/70">{t("trustMessage")}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
