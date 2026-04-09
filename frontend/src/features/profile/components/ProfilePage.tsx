"use client";

import { useTranslations, useLocale } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { useProfile } from "../hooks/use-profile";

function formatCurrency(kopiykas: number, locale: string): string {
  return new Intl.NumberFormat(locale === "uk" ? "uk-UA" : "en-US", {
    style: "currency",
    currency: "UAH",
  }).format(kopiykas / 100);
}

export function ProfilePage() {
  const t = useTranslations("profile");
  const locale = useLocale();
  const { profile, isLoading, isError, isNotFound } = useProfile();

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
