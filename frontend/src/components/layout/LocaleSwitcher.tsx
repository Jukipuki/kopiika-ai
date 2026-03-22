"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter, usePathname } from "@/i18n/navigation";
import { useTransition } from "react";
import { toast } from "sonner";
import { routing } from "@/i18n/routing";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const localeLabels: Record<string, { label: string; flag: string }> = {
  uk: { label: "Українська", flag: "🇺🇦" },
  en: { label: "English", flag: "🇬🇧" },
};

interface LocaleSwitcherProps {
  accessToken?: string | null;
}

export default function LocaleSwitcher({ accessToken }: LocaleSwitcherProps) {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations("settings");
  const [isPending, startTransition] = useTransition();

  const nextLocale = locale === "uk" ? "en" : "uk";
  const current = localeLabels[locale] || localeLabels.uk;
  const next = localeLabels[nextLocale];

  const handleSwitch = async () => {
    let saved = !accessToken; // No need to save if unauthenticated

    // Persist preference to backend if authenticated
    if (accessToken) {
      try {
        const res = await fetch(`${API_URL}/api/v1/auth/me`, {
          method: "PATCH",
          headers: {
            Authorization: `Bearer ${accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ locale: nextLocale }),
        });
        saved = res.ok;
      } catch {
        // Continue with locale switch even if backend call fails
      }
    }

    startTransition(() => {
      router.replace(pathname, { locale: nextLocale as (typeof routing.locales)[number] });
    });

    if (saved) {
      toast.success(t("preferenceSaved"), { duration: 2000 });
    }
  };

  return (
    <button
      onClick={handleSwitch}
      disabled={isPending}
      aria-label={`${t("language")}: ${current.label}. Switch to ${next.label}`}
      className="inline-flex items-center gap-1.5 rounded-lg border border-foreground/20 px-2.5 py-1.5 text-sm text-foreground/70 hover:bg-foreground/5 hover:text-foreground transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[#6C63FF]"
    >
      <span aria-hidden="true">{current.flag}</span>
      <span>{locale.toUpperCase()}</span>
    </button>
  );
}
