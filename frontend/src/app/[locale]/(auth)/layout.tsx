"use client";

import { useLocale } from "next-intl";
import { useRouter, usePathname } from "@/i18n/navigation";
import { useTransition } from "react";
import { routing } from "@/i18n/routing";

function AuthLocaleToggle() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const [isPending, startTransition] = useTransition();

  const nextLocale = locale === "uk" ? "en" : "uk";

  const handleSwitch = () => {
    startTransition(() => {
      router.replace(pathname, { locale: nextLocale as (typeof routing.locales)[number] });
    });
  };

  return (
    <div className="absolute top-4 right-4">
      <button
        onClick={handleSwitch}
        disabled={isPending}
        aria-label={`Switch language to ${nextLocale === "uk" ? "Українська" : "English"}`}
        className="text-sm text-foreground/50 hover:text-foreground transition-colors focus:outline-none focus:ring-2 focus:ring-[#6C63FF] rounded px-1"
      >
        <span className={locale === "uk" ? "font-semibold text-foreground" : ""}>
          UA
        </span>
        {" | "}
        <span className={locale === "en" ? "font-semibold text-foreground" : ""}>
          EN
        </span>
      </button>
    </div>
  );
}

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="relative flex min-h-screen items-center justify-center bg-background px-4 py-8">
      <AuthLocaleToggle />
      <div className="w-full max-w-md rounded-2xl border border-foreground/10 bg-background p-8 shadow-lg sm:p-10">
        {children}
      </div>
    </div>
  );
}
