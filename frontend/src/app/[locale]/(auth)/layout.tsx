"use client";

import { useLocale } from "next-intl";
import { usePathname } from "@/i18n/navigation";

function AuthLocaleToggle() {
  const locale = useLocale();
  const pathname = usePathname();

  const nextLocale = locale === "uk" ? "en" : "uk";

  const handleSwitch = () => {
    window.location.href = `/${nextLocale}${pathname}`;
  };

  return (
    <div className="absolute top-4 right-4">
      <button
        onClick={handleSwitch}
        disabled={false}
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
