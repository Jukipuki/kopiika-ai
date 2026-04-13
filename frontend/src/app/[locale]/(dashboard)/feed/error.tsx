"use client";

// Route-level error boundary (Next.js error.tsx convention).
// Keep UI in sync with FeatureErrorBoundary in @/components/error/FeatureErrorBoundary.tsx
// which handles component-level errors inside the page.

import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function FeedError({
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  const t = useTranslations("errors.boundary");

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <Card>
        <CardContent className="p-6 text-center">
          <p className="mb-4 text-sm text-muted-foreground">{t("feed")}</p>
          <Button variant="ghost" size="sm" onClick={reset}>
            {t("retry")}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
