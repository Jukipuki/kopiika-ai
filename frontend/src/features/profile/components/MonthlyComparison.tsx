"use client";

import { useTranslations, useLocale } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCurrency } from "../format";
import type { MonthlyComparison as MonthlyComparisonType } from "../types";

function formatMonth(yearMonth: string, locale: string): string {
  const [year, month] = yearMonth.split("-").map(Number);
  const date = new Date(year, month - 1);
  return new Intl.DateTimeFormat(locale === "uk" ? "uk-UA" : "en-US", {
    year: "numeric",
    month: "long",
  }).format(date);
}

function ChangeIndicator({
  changePercent,
  t,
}: {
  changePercent: number;
  t: ReturnType<typeof useTranslations>;
}) {
  if (changePercent > 0) {
    return (
      <span className="inline-flex items-center gap-1 text-red-500">
        <span aria-hidden="true">↑</span>
        <span>+{Math.round(changePercent)}%</span>
        <span className="sr-only">{t("increase")}</span>
      </span>
    );
  }
  if (changePercent < 0) {
    return (
      <span className="inline-flex items-center gap-1 text-green-600">
        <span aria-hidden="true">↓</span>
        <span>{Math.round(changePercent)}%</span>
        <span className="sr-only">{t("decrease")}</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-muted-foreground">
      <span aria-hidden="true">–</span>
      <span>0%</span>
      <span className="sr-only">{t("noChange")}</span>
    </span>
  );
}

export function MonthlyComparison({
  data,
}: {
  data: MonthlyComparisonType;
}) {
  const t = useTranslations("profile.monthlyComparison");
  const locale = useLocale();

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
        <p className="text-sm text-muted-foreground">
          {t("subtitle", {
            current: formatMonth(data.currentMonth, locale),
            previous: formatMonth(data.previousMonth, locale),
          })}
        </p>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {data.categories.map((cat) => (
            <li
              key={cat.category}
              className="flex items-center justify-between border-b border-foreground/5 pb-2 last:border-0"
            >
              <span className="text-sm capitalize">
                {cat.category === "uncategorized"
                  ? t("uncategorized")
                  : cat.category}
              </span>
              <span className="flex items-center gap-2">
                <span className="text-sm font-medium">
                  {formatCurrency(cat.currentAmount, locale)}
                </span>
                <ChangeIndicator changePercent={cat.changePercent} t={t} />
              </span>
            </li>
          ))}
        </ul>

        {/* Total row */}
        <div className="mt-4 flex items-center justify-between border-t pt-4">
          <span className="text-sm font-bold">{t("totalLabel")}</span>
          <span className="flex items-center gap-2">
            <span className="text-sm font-bold">
              {formatCurrency(data.totalCurrent, locale)}
            </span>
            <ChangeIndicator
              changePercent={data.totalChangePercent}
              t={t}
            />
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
