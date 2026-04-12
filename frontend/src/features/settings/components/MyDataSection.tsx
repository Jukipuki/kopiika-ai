"use client";

import { useTranslations, useLocale } from "next-intl";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { formatDateLong } from "@/lib/format/date";
import { formatCurrency } from "@/features/profile/format";
import { useDataSummary } from "../hooks/use-data-summary";

export default function MyDataSection() {
  const t = useTranslations("settings.myData");
  const tErrors = useTranslations("errors");
  const locale = useLocale();
  const { data, isLoading, error, refetch } = useDataSummary();

  if (isLoading) {
    return (
      <section aria-labelledby="my-data-heading">
        <Card>
          <CardHeader>
            <h2 id="my-data-heading" className="text-lg font-medium leading-snug">
              {t("title")}
            </h2>
          </CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </CardContent>
        </Card>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-labelledby="my-data-heading">
        <Card>
          <CardHeader>
            <h2 id="my-data-heading" className="text-lg font-medium leading-snug">
              {t("title")}
            </h2>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-4 py-8">
            <p className="text-muted-foreground">{tErrors("serverError")}</p>
            <Button onClick={refetch} className="min-h-[44px] min-w-[44px]">
              {tErrors("retry")}
            </Button>
          </CardContent>
        </Card>
      </section>
    );
  }

  if (!data) return null;

  return (
    <section aria-labelledby="my-data-heading">
      <Card>
        <CardHeader>
          <h2 id="my-data-heading" className="text-lg font-medium leading-snug">
            {t("title")}
          </h2>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1">
              <span className="text-sm text-muted-foreground">{t("uploads")}</span>
              <p className="text-lg font-semibold">{data.uploadCount}</p>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-sm text-muted-foreground">{t("transactions")}</span>
              <p className="text-lg font-semibold">{data.transactionCount}</p>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-sm text-muted-foreground">{t("insights")}</span>
              <p className="text-lg font-semibold">{data.insightCount}</p>
            </div>
          </div>

          {data.transactionDateRange && (
            <>
              <Separator />
              <div className="flex flex-col gap-1">
                <span className="text-sm text-muted-foreground">{t("dateRange")}</span>
                <p>
                  {formatDateLong(data.transactionDateRange.earliest, locale)} —{" "}
                  {formatDateLong(data.transactionDateRange.latest, locale)}
                </p>
              </div>
            </>
          )}

          {data.categoriesDetected.length > 0 && (
            <>
              <Separator />
              <div className="flex flex-col gap-1">
                <span className="text-sm text-muted-foreground">{t("categories")}</span>
                <p>{data.categoriesDetected.join(", ")}</p>
              </div>
            </>
          )}

          {data.financialProfile && (
            <>
              <Separator />
              <div className="flex flex-col gap-1">
                <span className="text-sm text-muted-foreground">{t("financialProfile")}</span>
                <div className="grid grid-cols-2 gap-2 mt-1">
                  <div>
                    <span className="text-xs text-muted-foreground">{t("income")}</span>
                    <p className="text-sm font-medium">{formatCurrency(data.financialProfile.totalIncome, locale)}</p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">{t("expenses")}</span>
                    <p className="text-sm font-medium">{formatCurrency(Math.abs(data.financialProfile.totalExpenses), locale)}</p>
                  </div>
                </div>
              </div>
            </>
          )}

          {data.healthScoreHistory.length > 0 && (
            <>
              <Separator />
              <div className="flex flex-col gap-1">
                <span className="text-sm text-muted-foreground">{t("healthScores")}</span>
                <p>
                  {t("healthScoreCount", { count: data.healthScoreHistory.length })}
                </p>
              </div>
            </>
          )}

          {data.consentRecords.length > 0 && (
            <>
              <Separator />
              <div className="flex flex-col gap-1">
                <span className="text-sm text-muted-foreground">{t("consents")}</span>
                <ul className="space-y-1">
                  {data.consentRecords.map((record, i) => (
                    <li key={i} className="text-sm">
                      {record.consentType} — {formatDateLong(record.grantedAt, locale)}
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}

          {data.uploadCount === 0 && (
            <p className="text-sm text-muted-foreground">{t("empty")}</p>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
