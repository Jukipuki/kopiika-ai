"use client";

import { useTranslations } from "next-intl";
import { FileText } from "lucide-react";

export default function FileFormatGuide() {
  const t = useTranslations("upload");

  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <FileText className="h-4 w-4" />
      <span>{t("supportedFormat")}</span>
    </div>
  );
}
