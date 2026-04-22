"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { Card, CardContent } from "@/components/ui/card";
import { useReviewQueueCount } from "../hooks/use-review-queue-count";

export default function ReviewQueueSection() {
  const t = useTranslations("settings.reviewQueue");
  const { count, isLoading } = useReviewQueueCount();

  // Hide entirely when nothing to review — AC #8 requires absence, not "0 pending".
  if (isLoading || count === 0) return null;

  return (
    <section aria-labelledby="review-queue-heading">
      <Card>
        <CardContent className="flex items-center justify-between gap-4 py-4">
          <div className="flex flex-col">
            <h2
              id="review-queue-heading"
              className="text-base font-medium leading-snug"
            >
              {t("title", { count })}
            </h2>
            <p className="text-sm text-muted-foreground">{t("description")}</p>
          </div>
          <Link
            href="/settings/review-queue"
            className="text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            {t("openLink")}
          </Link>
        </CardContent>
      </Card>
    </section>
  );
}
