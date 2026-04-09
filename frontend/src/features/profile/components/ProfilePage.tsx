"use client";

import { useTranslations, useLocale } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { useHealthScore } from "../hooks/use-health-score";
import { useHealthScoreHistory } from "../hooks/use-health-score-history";
import { useMonthlyComparison } from "../hooks/use-monthly-comparison";
import { useProfile } from "../hooks/use-profile";
import { formatCurrency } from "../format";
import { HealthScoreRing } from "./HealthScoreRing";
import { HealthScoreTrend } from "./HealthScoreTrend";
import { MonthlyComparison } from "./MonthlyComparison";

export function ProfilePage() {
  const t = useTranslations("profile");
  const locale = useLocale();
  const { profile, isLoading, isError, isNotFound } = useProfile();
  const {
    healthScore,
    isLoading: isHealthScoreLoading,
    isNotFound: isHealthScoreNotFound,
  } = useHealthScore();
  const {
    history,
    isLoading: isHistoryLoading,
  } = useHealthScoreHistory();
  const {
    comparison,
    isLoading: isComparisonLoading,
    isError: isComparisonError,
  } = useMonthlyComparison();

  if (isLoading) {
    return <ProfileSkeleton />;
  }

  if (isNotFound) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground mb-4">{t("noProfile")}</p>
        <Link
          href="/upload"
          className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          {t("goToUpload")}
        </Link>
      </div>
    );
  }

  if (isError || !profile) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive">{t("loadFailed")}</p>
      </div>
    );
  }

  const netBalance = profile.totalIncome + profile.totalExpenses;
  const categories = Object.entries(profile.categoryTotals).sort(
    ([, a], [, b]) => a - b
  );

  return (
    <div className="space-y-6">
      {/* Health Score Section */}
      <Card>
        <CardHeader>
          <CardTitle>{t("healthScore.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          {isHealthScoreLoading ? (
            <div className="flex flex-col items-center gap-4">
              <Skeleton className="h-40 w-40 rounded-full" />
              <Skeleton className="h-4 w-32" />
            </div>
          ) : isHealthScoreNotFound || !healthScore ? (
            <p className="text-center text-sm text-muted-foreground">
              {t("healthScore.noScore")}
            </p>
          ) : (
            <HealthScoreRing
              score={healthScore.score}
              breakdown={healthScore.breakdown}
            />
          )}
          {healthScore && (
            isHistoryLoading ? (
              <Skeleton className="h-[120px] w-full mt-4 rounded" />
            ) : (
              <HealthScoreTrend data={history} locale={locale} />
            )
          )}
        </CardContent>
      </Card>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>{t("totalIncome")}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-green-600">
              {formatCurrency(profile.totalIncome, locale)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("totalExpenses")}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-red-600">
              {formatCurrency(Math.abs(profile.totalExpenses), locale)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("netBalance")}</CardTitle>
          </CardHeader>
          <CardContent>
            <p
              className={`text-2xl font-bold ${netBalance >= 0 ? "text-green-600" : "text-red-600"}`}
            >
              {formatCurrency(netBalance, locale)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Period info */}
      {profile.periodStart && profile.periodEnd && (
        <p className="text-sm text-muted-foreground">
          {t("period", {
            start: new Date(profile.periodStart).toLocaleDateString(
              locale === "uk" ? "uk-UA" : "en-US"
            ),
            end: new Date(profile.periodEnd).toLocaleDateString(
              locale === "uk" ? "uk-UA" : "en-US"
            ),
          })}
        </p>
      )}

      {/* Month-over-Month Comparison */}
      {isComparisonLoading ? (
        <Card>
          <CardHeader>
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex justify-between">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-20" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : isComparisonError ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("monthlyComparison.title")}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-destructive">
              {t("monthlyComparison.loadFailed")}
            </p>
          </CardContent>
        </Card>
      ) : comparison ? (
        <MonthlyComparison data={comparison} />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>{t("monthlyComparison.title")}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {t("monthlyComparison.noData")}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Category breakdown */}
      {categories.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>{t("categoryBreakdown")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {categories.map(([category, amount]) => (
                <li
                  key={category}
                  className="flex items-center justify-between border-b border-foreground/5 pb-2 last:border-0"
                >
                  <span className="text-sm capitalize">{category}</span>
                  <span
                    className={`text-sm font-medium ${amount >= 0 ? "text-green-600" : "text-red-600"}`}
                  >
                    {formatCurrency(amount, locale)}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ProfileSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-32" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-40" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="flex justify-between">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-16" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
