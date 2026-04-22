"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/features/profile/format";
import { useCategoryLabel } from "@/features/profile/format";
import {
  MatrixViolationError,
  ReviewQueueEntry,
  useDismissQueueEntry,
  useResolveQueueEntry,
  useReviewQueue,
} from "../hooks/use-review-queue";

// 19-category taxonomy (tech spec §2.3) — kept inline since no picker
// component exists yet. Tracked as TD-063 for future polish.
const CATEGORIES = [
  "groceries",
  "restaurants",
  "transport",
  "entertainment",
  "utilities",
  "healthcare",
  "shopping",
  "travel",
  "education",
  "finance",
  "subscriptions",
  "fuel",
  "atm_cash",
  "government",
  "transfers",
  "transfers_p2p",
  "savings",
  "charity",
  "other",
] as const;

const KINDS = ["spending", "income", "savings", "transfer"] as const;

function percentLabel(confidence: number): number {
  return Math.round(confidence * 100);
}

function formatLocalisedDate(isoDate: string, locale: string): string {
  return new Date(isoDate).toLocaleDateString(
    locale === "uk" ? "uk-UA" : "en-US",
    { year: "numeric", month: "short", day: "numeric" },
  );
}

function EntryRow({
  entry,
}: {
  entry: ReviewQueueEntry;
}) {
  const t = useTranslations("settings.reviewQueue");
  const tKinds = useTranslations("settings.reviewQueue.kinds");
  const locale = useLocale();
  const categoryLabel = useCategoryLabel();

  const resolveMutation = useResolveQueueEntry();
  const dismissMutation = useDismissQueueEntry();

  const [editing, setEditing] = useState(false);
  const [category, setCategory] = useState(entry.suggestedCategory ?? "other");
  const [kind, setKind] = useState(entry.suggestedKind ?? "spending");
  const [inlineError, setInlineError] = useState<string | null>(null);

  const onResolve = () => {
    setInlineError(null);
    resolveMutation.mutate(
      { entryId: entry.id, category, kind },
      {
        onError: (err) => {
          if (err instanceof MatrixViolationError) {
            setInlineError(t("matrixError"));
          } else {
            setInlineError(t("resolveError"));
          }
        },
      },
    );
  };

  const onDismiss = () => {
    dismissMutation.mutate(entry.id);
  };

  return (
    <Card className="mb-3">
      <CardContent className="flex flex-col gap-3 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <span className="text-sm font-medium">{entry.description}</span>
            <span className="text-xs text-muted-foreground">
              {formatLocalisedDate(entry.date, locale)}
            </span>
            {entry.suggestedCategory && (
              <span className="text-xs text-muted-foreground">
                {t("suggestedLabel")}: {categoryLabel(entry.suggestedCategory)}
                {entry.suggestedKind ? ` · ${tKinds(entry.suggestedKind)}` : ""}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium tabular-nums">
              {t("confidenceLabel", { percent: percentLabel(entry.categorizationConfidence) })}
            </span>
            <span className="text-sm font-semibold tabular-nums">
              {formatCurrency(entry.amount, locale)}
            </span>
          </div>
        </div>

        {editing ? (
          <div className="flex flex-col gap-2">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-muted-foreground">{t("categoryLabel")}</span>
                <select
                  aria-label={t("categoryLabel")}
                  className="min-h-[36px] rounded border border-input bg-background px-2 text-sm"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {categoryLabel(c)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-muted-foreground">{t("kindLabel")}</span>
                <select
                  aria-label={t("kindLabel")}
                  className="min-h-[36px] rounded border border-input bg-background px-2 text-sm"
                  value={kind}
                  onChange={(e) => setKind(e.target.value)}
                >
                  {KINDS.map((k) => (
                    <option key={k} value={k}>
                      {tKinds(k)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {inlineError && (
              <p className="text-xs text-destructive" role="alert">
                {inlineError}
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                onClick={onResolve}
                disabled={resolveMutation.isPending}
              >
                {t("resolveButton")}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setEditing(false);
                  setInlineError(null);
                  setCategory(entry.suggestedCategory ?? "other");
                  setKind(entry.suggestedKind ?? "spending");
                }}
                disabled={resolveMutation.isPending}
              >
                {t("cancelButton")}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => setEditing(true)}>
              {t("editButton")}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onDismiss}
              disabled={dismissMutation.isPending}
            >
              {t("dismissButton")}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function ReviewQueuePage() {
  const t = useTranslations("settings.reviewQueue");
  const { items, isLoading, isFetchingMore, hasMore, loadMore, error } =
    useReviewQueue();

  return (
    <main className="px-4 py-6 md:mx-auto md:max-w-2xl md:px-6 lg:max-w-3xl">
      <h1 className="mb-2 text-2xl font-semibold">{t("pageTitle")}</h1>
      <p className="mb-6 text-sm text-muted-foreground">{t("pageDescription")}</p>

      {isLoading && (
        <div className="space-y-3" data-testid="review-queue-skeleton">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </div>
      )}

      {!isLoading && error && (
        <Card>
          <CardContent className="py-6 text-center text-sm text-muted-foreground">
            {t("loadError")}
          </CardContent>
        </Card>
      )}

      {!isLoading && !error && items.length === 0 && (
        <Card>
          <CardContent className="py-6 text-center text-sm text-muted-foreground">
            {t("empty")}
          </CardContent>
        </Card>
      )}

      {!isLoading && !error && items.length > 0 && (
        <div>
          {items.map((entry) => (
            <EntryRow key={entry.id} entry={entry} />
          ))}
          {hasMore && (
            <div className="mt-4 flex justify-center">
              <Button
                variant="outline"
                onClick={() => loadMore()}
                disabled={isFetchingMore}
              >
                {t("loadMore")}
              </Button>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
