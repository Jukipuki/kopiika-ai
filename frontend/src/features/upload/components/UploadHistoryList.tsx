"use client";

import { useTranslations } from "next-intl";
import { FileText, CheckCircle2, Clock, AlertCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useUploadHistory } from "../hooks/use-upload-history";
import type { UploadHistoryItem } from "../hooks/use-upload-history";

const FORMAT_LABELS: Record<string, string> = {
  monobank: "Monobank",
  privatbank: "PrivatBank",
  unknown: "CSV",
};

function StatusBadge({ status }: { status: string }) {
  const t = useTranslations("history");

  switch (status) {
    case "completed":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
          <CheckCircle2 className="h-3 w-3" />
          {t("statusCompleted")}
        </span>
      );
    case "processing":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
          <Clock className="h-3 w-3" />
          {t("statusProcessing")}
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
          <AlertCircle className="h-3 w-3" />
          {t("statusFailed")}
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-400">
          <Clock className="h-3 w-3" />
          {status}
        </span>
      );
  }
}

function UploadRow({ item }: { item: UploadHistoryItem }) {
  const t = useTranslations("history");

  const formatLabel = item.detectedFormat
    ? FORMAT_LABELS[item.detectedFormat] || item.detectedFormat
    : "—";

  const date = new Date(item.createdAt);
  const formattedDate = date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
  const formattedTime = date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="flex items-center gap-4 border-b border-foreground/5 px-4 py-3 last:border-b-0">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
        <FileText className="h-5 w-5 text-primary" />
      </div>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-foreground">{item.fileName}</p>
        <p className="text-xs text-muted-foreground">
          {formatLabel} &middot; {formattedDate} {formattedTime}
        </p>
      </div>

      <div className="shrink-0 text-right">
        <p className="text-sm font-medium text-foreground">
          {t("transactionCount", { count: item.transactionCount })}
        </p>
        {item.duplicatesSkipped > 0 && (
          <p className="text-xs text-muted-foreground">
            {t("duplicatesSkipped", { count: item.duplicatesSkipped })}
          </p>
        )}
      </div>

      <div className="shrink-0">
        <StatusBadge status={item.status} />
      </div>
    </div>
  );
}

export default function UploadHistoryList() {
  const t = useTranslations("history");
  const { uploads, total, isLoading, isFetchingMore, error, hasMore, loadMore } = useUploadHistory();

  if (isLoading && uploads.length === 0) {
    return (
      <Card className="mx-auto w-full max-w-[800px]">
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="mx-auto w-full max-w-[800px]">
        <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
          <AlertCircle className="h-8 w-8 text-destructive" />
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (uploads.length === 0) {
    return (
      <Card className="mx-auto w-full max-w-[800px]">
        <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
          <FileText className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{t("noUploads")}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="mx-auto w-full max-w-[800px]">
      <CardHeader>
        <CardTitle className="text-base">
          {t("title")} ({total})
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div>
          {uploads.map((item) => (
            <UploadRow key={item.id} item={item} />
          ))}
        </div>

        {hasMore && (
          <div className="flex justify-center border-t border-foreground/5 p-4">
            <Button
              variant="outline"
              size="sm"
              onClick={loadMore}
              disabled={isFetchingMore}
            >
              {isFetchingMore ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              {t("loadMore")}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
