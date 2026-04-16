"use client";

import { useTranslations, useLocale } from "next-intl";
import { CheckCircle2, History, ArrowRight } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { formatDateLong } from "@/lib/format/date";
import type { DateRange } from "../types";

interface UploadSummaryCardProps {
  bankName: string | null;
  transactionCount: number;
  dateRange: DateRange | null;
  totalInsights: number;
  duplicatesSkipped: number;
  newTransactions: number;
  fallbackBankLabel?: string | null;
  onUploadAnother: () => void;
}

export default function UploadSummaryCard({
  bankName,
  transactionCount,
  dateRange,
  totalInsights,
  duplicatesSkipped,
  newTransactions,
  fallbackBankLabel,
  onUploadAnother,
}: UploadSummaryCardProps) {
  const t = useTranslations("upload");
  const summaryT = useTranslations("upload.summary");
  const locale = useLocale();

  const bankDetectedLabel =
    bankName && bankName.length > 0
      ? summaryT("bankDetected", { bankName })
      : fallbackBankLabel ?? null;

  const formattedDateRange = dateRange
    ? summaryT("dateRange", {
        start: formatDateLong(dateRange.start, locale),
        end: formatDateLong(dateRange.end, locale),
      })
    : null;

  return (
    <div
      className="flex w-full flex-col items-center gap-3 text-center"
      data-testid="upload-summary-card"
    >
      <CheckCircle2 className="h-10 w-10 text-green-500" aria-hidden="true" />
      <h2 className="text-base font-semibold text-foreground">{summaryT("title")}</h2>

      {bankDetectedLabel && (
        <p className="text-xs text-muted-foreground">{bankDetectedLabel}</p>
      )}

      <p className="text-sm text-foreground">
        {summaryT("transactionCount", { count: transactionCount })}
      </p>

      {formattedDateRange && (
        <p className="text-xs text-muted-foreground">{formattedDateRange}</p>
      )}

      <p className="text-sm text-foreground">
        {summaryT("insightCount", { count: totalInsights })}
      </p>

      {(newTransactions > 0 || duplicatesSkipped > 0) && (
        <p className="text-xs text-muted-foreground">
          {t("completionSummary", {
            newCount: newTransactions,
            skippedCount: duplicatesSkipped,
          })}
        </p>
      )}

      <Link
        href="/feed"
        className={buttonVariants({ size: "lg" }) + " mt-2 min-h-[44px] gap-2"}
      >
        {summaryT("viewInsights")}
        <ArrowRight className="h-4 w-4" aria-hidden="true" />
      </Link>

      <div className="flex items-center gap-3 pt-1">
        <Button
          variant="outline"
          size="sm"
          onClick={onUploadAnother}
          className="min-h-[44px]"
        >
          {t("uploadAnother")}
        </Button>
        <Link
          href="/history"
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <History className="h-3.5 w-3.5" aria-hidden="true" />
          {t("viewHistory")}
        </Link>
      </div>
    </div>
  );
}
