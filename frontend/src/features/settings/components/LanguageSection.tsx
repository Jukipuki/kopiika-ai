"use client";

import { useTranslations, useLocale } from "next-intl";
import { usePathname } from "@/i18n/navigation";
import { useSession } from "next-auth/react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LanguageSection() {
  const t = useTranslations("settings");
  const locale = useLocale();
  const pathname = usePathname();
  const { data: session } = useSession();

  const handleLanguageChange = async (newLocale: string | null) => {
    if (!newLocale || newLocale === locale) return;

    let saved = !session?.accessToken;

    if (session?.accessToken) {
      try {
        const res = await fetch(`${API_URL}/api/v1/auth/me`, {
          method: "PATCH",
          headers: {
            Authorization: `Bearer ${session.accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ locale: newLocale }),
        });
        saved = res.ok;
      } catch {
        // Continue with locale switch even if backend call fails
      }
    }

    if (saved) {
      toast.success(t("preferenceSaved"), { duration: 2000 });
    } else {
      toast.error(t("saveFailed"), { duration: 4000 });
    }

    // Full navigation to ensure middleware runs and locale state is consistent
    window.location.href = `/${newLocale}${pathname}`;
  };

  return (
    <section aria-labelledby="language-heading">
      <Card>
        <CardHeader>
          <h2 id="language-heading" className="text-lg font-medium leading-snug">
            {t("languagePreference")}
          </h2>
          <p className="text-sm text-muted-foreground">
            {t("languageDescription")}
          </p>
        </CardHeader>
        <CardContent>
          <Select
            value={locale}
            onValueChange={handleLanguageChange}
            disabled={false}
          >
            <SelectTrigger
              className="w-full min-h-[44px] sm:w-[240px]"
              aria-label={t("languagePreference")}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="uk" className="min-h-[44px]">
                {t("ukrainian")}
              </SelectItem>
              <SelectItem value="en" className="min-h-[44px]">
                {t("english")}
              </SelectItem>
            </SelectContent>
          </Select>
        </CardContent>
      </Card>
    </section>
  );
}
