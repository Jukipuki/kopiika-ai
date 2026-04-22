"use client";

import {
  unstable_catchError as catchError,
  type ErrorInfo,
} from "next/error";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type FeatureArea = "feed" | "profile" | "upload" | "settings" | "review-queue";

function ErrorFallback(
  props: { feature: FeatureArea },
  { error, unstable_retry: retry }: ErrorInfo,
) {
  const t = useTranslations("errors.boundary");

  console.error(`[FeatureErrorBoundary:${props.feature}]`, error);

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <Card>
        <CardContent className="p-6 text-center">
          <p className="mb-4 text-sm text-muted-foreground">
            {t(props.feature)}
          </p>
          <Button variant="ghost" size="sm" onClick={() => retry()}>
            {t("retry")}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default catchError(ErrorFallback);
