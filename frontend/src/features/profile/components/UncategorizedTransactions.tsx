"use client";

import { useTranslations, useLocale } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useFlaggedTransactions } from "../hooks/use-flagged-transactions";
import { formatAmountOnly, formatCurrency } from "../format";

const KNOWN_REASONS = new Set([
  "low_confidence",
  "parse_failure",
  "llm_unavailable",
  "currency_unknown",
]);

export function UncategorizedTransactions() {
  const t = useTranslations("profile");
  const locale = useLocale();
  const { flaggedTransactions, isLoading, isError } = useFlaggedTransactions();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-64" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex justify-between">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-4 w-20" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isError || flaggedTransactions.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("uncategorized.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-4">
          {t("uncategorized.explanation")}
        </p>
        <div className="space-y-3">
          {flaggedTransactions.map((txn) => (
            <div key={txn.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 border-b pb-3 last:border-0 last:pb-0">
              <div className="flex flex-col">
                <span className="text-sm font-medium">{txn.description}</span>
                <span className="text-xs text-muted-foreground">
                  {new Date(txn.date).toLocaleDateString(
                    locale === "uk" ? "uk-UA" : "en-US"
                  )}
                </span>
                {txn.uncategorizedReason && (
                  <span className="text-xs text-muted-foreground italic flex items-center gap-2">
                    <span>
                      {KNOWN_REASONS.has(txn.uncategorizedReason)
                        ? t(`uncategorized.reason.${txn.uncategorizedReason}`)
                        : txn.uncategorizedReason.replace(/_/g, " ")}
                    </span>
                    {txn.currencyUnknownRaw && (
                      <span className="font-mono not-italic rounded border border-border px-1.5 py-0 text-[10px] uppercase">
                        {txn.currencyUnknownRaw}
                      </span>
                    )}
                  </span>
                )}
              </div>
              <span className="text-sm font-semibold tabular-nums">
                {txn.currencyUnknownRaw
                  ? formatAmountOnly(txn.amount, locale)
                  : formatCurrency(txn.amount, locale)}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
