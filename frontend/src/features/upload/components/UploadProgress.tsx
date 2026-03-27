"use client";

import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";

export default function UploadProgress() {
  const t = useTranslations("upload");

  return (
    <div className="flex flex-col items-center gap-3 py-4">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
      <p className="text-sm font-medium text-foreground">
        {t("analyzing")}
      </p>
    </div>
  );
}
