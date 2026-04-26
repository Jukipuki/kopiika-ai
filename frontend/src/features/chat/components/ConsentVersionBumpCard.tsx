"use client";

import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

interface Props {
  onAccept: () => void;
  isGranting: boolean;
}

export function ConsentVersionBumpCard({ onAccept, isGranting }: Props) {
  const t = useTranslations("chat");
  return (
    <div
      role="region"
      aria-labelledby="chat-consent-bump-title"
      className="m-4 rounded-lg border border-border/60 bg-card p-4 text-sm"
    >
      <p id="chat-consent-bump-title" className="font-medium">
        {t("consent.version_bump.title")}
      </p>
      <p className="mt-1 text-muted-foreground">{t("consent.version_bump.body")}</p>
      <div className="mt-3 flex justify-end">
        <Button onClick={onAccept} disabled={isGranting}>
          {t("consent.version_bump.accept")}
        </Button>
      </div>
    </div>
  );
}
