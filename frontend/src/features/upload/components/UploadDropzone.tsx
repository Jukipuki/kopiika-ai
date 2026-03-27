"use client";

import { useState, useCallback, useRef } from "react";
import { useTranslations } from "next-intl";
import { Upload, FileUp, AlertCircle, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useUpload } from "../hooks/use-upload";
import UploadProgress from "./UploadProgress";
import FileFormatGuide from "./FileFormatGuide";
import type { UploadState } from "../types";

const ALLOWED_EXTENSIONS = [".csv", ".pdf"];
const ACCEPT = ".csv,.pdf,text/csv,application/pdf";

export default function UploadDropzone() {
  const t = useTranslations("upload");
  const { upload, isUploading, error, clearError } = useUpload();
  const [dragState, setDragState] = useState<UploadState>("idle");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadComplete, setUploadComplete] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounterRef = useRef(0);

  const getState = (): UploadState => {
    if (error) return "error";
    if (isUploading) return "uploading";
    if (dragState === "drag-over") return "drag-over";
    if (selectedFile) return "selected";
    return "idle";
  };

  const handleFile = useCallback(
    async (file: File) => {
      clearError();
      setSelectedFile(file);
      setUploadComplete(false);

      const result = await upload(file);
      if (result) {
        setUploadComplete(true);
        toast.success(t("uploadSuccess"));
        // Reset after showing success
        setTimeout(() => {
          setSelectedFile(null);
          setUploadComplete(false);
        }, 2000);
      }
    },
    [upload, clearError, t],
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
    if (!isUploading) {
      fileInputRef.current?.click();
    }
  }, [isUploading]);

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

  const errorKey = error
    ? error.code === "INVALID_FILE_TYPE"
      ? "errorInvalidFileType"
      : error.code === "FILE_TOO_LARGE"
        ? "errorFileTooLarge"
        : error.code === "RATE_LIMITED"
          ? "errorRateLimited"
          : "errorUploadFailed"
    : null;
  const errorMessage = errorKey ? t(errorKey) : null;

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

          {state === "uploading" && <UploadProgress />}

          {state === "error" && (
            <div className="flex flex-col items-center gap-3 text-center">
              <AlertCircle className="h-10 w-10 text-destructive" />
              <p className="text-sm text-destructive">{errorMessage}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  clearError();
                  setSelectedFile(null);
                }}
                className="min-h-[44px] min-w-[44px]"
              >
                {t("tryAgain")}
              </Button>
            </div>
          )}

          {uploadComplete && (
            <div className="flex flex-col items-center gap-3 text-center">
              <CheckCircle2 className="h-10 w-10 text-green-500" />
              <p className="text-sm font-medium text-foreground">{t("uploadSuccess")}</p>
            </div>
          )}

          {state === "selected" && !isUploading && !uploadComplete && (
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
