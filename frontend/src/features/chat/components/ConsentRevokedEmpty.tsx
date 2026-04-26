"use client";

import { useTranslations, useLocale } from "next-intl";

export function ConsentRevokedEmpty() {
  const t = useTranslations("chat");
  const locale = useLocale();
  const settingsHref = `/${locale}/settings`;
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <h2 className="text-lg font-semibold">{t("consent.revoked.title")}</h2>
      <p className="max-w-md text-sm text-muted-foreground">{t("consent.revoked.body")}</p>
      <a
        href={settingsHref}
        className="text-sm underline hover:text-foreground"
      >
        {t("consent.revoked.settings_link")}
      </a>
    </div>
  );
}
