"use client";

import { useTranslations, useLocale } from "next-intl";
import { CheckCircle2, History, ArrowRight } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { formatDateLong } from "@/lib/format/date";
import type { DateRange, RejectedRow, UploadWarning } from "../types";

interface UploadSummaryCardProps {
  bankName: string | null;
  transactionCount: number;
  dateRange: DateRange | null;
  totalInsights: number;
  duplicatesSkipped: number;
  newTransactions: number;
  fallbackBankLabel?: string | null;
  rejectedRows?: RejectedRow[];
  warnings?: UploadWarning[];
  onUploadAnother: () => void;
}

const REJECTION_REASON_KEYS = new Set([
  "date_out_of_range",
  "zero_or_null_amount",
  "no_identifying_info",
  "sign_convention_mismatch",
]);

export default function UploadSummaryCard({
  bankName,
  transactionCount,
  dateRange,
  totalInsights,
  duplicatesSkipped,
  newTransactions,
  fallbackBankLabel,
  rejectedRows = [],
  warnings = [],
  onUploadAnother,
}: UploadSummaryCardProps) {
  const t = useTranslations("upload");
  const summaryT = useTranslations("upload.summary");
  const locale = useLocale();

  const reasonLabel = (reason: string): string => {
    const key = REJECTION_REASON_KEYS.has(reason)
      ? `rejectedReason_${reason}`
      : "rejectedReason_unknown";
    return summaryT(key);
  };

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

      {rejectedRows.length > 0 && (
        <details
          className="w-full rounded-md border border-amber-300/60 bg-amber-50 px-3 py-2 text-left dark:border-amber-700/40 dark:bg-amber-950/30"
          data-testid="rejected-rows-section"
        >
          <summary className="cursor-pointer text-xs font-medium text-amber-900 dark:text-amber-200">
            {summaryT("rejectedRowsTitle", { count: rejectedRows.length })}
          </summary>
          <ul className="mt-2 flex flex-col gap-1 text-xs text-amber-900/90 dark:text-amber-200/90">
            {rejectedRows.map((row) => (
              <li key={row.row_number}>
                {summaryT("rejectedRowsRow", {
                  row: row.row_number,
                  reason: reasonLabel(row.reason),
                })}
              </li>
            ))}
          </ul>
        </details>
      )}

      {warnings.length > 0 && (
        <p
          className="text-xs text-amber-700 dark:text-amber-300"
          data-testid="upload-warnings-note"
        >
          {summaryT("warningsTitle", { count: warnings.length })}
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
