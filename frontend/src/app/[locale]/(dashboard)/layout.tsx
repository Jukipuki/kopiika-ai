"use client";

import { signOut, useSession } from "next-auth/react";
import { useTranslations, useLocale } from "next-intl";
import { usePathname } from "next/navigation";
import { toast } from "sonner";
import AuthGuard from "@/lib/auth/auth-guard";
import ConsentGuard from "@/lib/auth/consent-guard";
import { useIdleTimeout } from "@/features/auth/hooks/use-idle-timeout";
import SessionExpiredDialog from "@/features/auth/components/SessionExpiredDialog";
import LocaleSwitcher from "@/components/layout/LocaleSwitcher";
import AppVersionBadge from "@/components/AppVersionBadge";
import { Link } from "@/i18n/navigation";
import { Settings, Plus, History, BookOpen, User } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: session } = useSession();
  const locale = useLocale();
  const t = useTranslations("dashboard");
  const pathname = usePathname();
  // Onboarding routes render a minimal layout without dashboard chrome
  // (header nav, upload FAB). Users who haven't consented must not see the
  // main nav — see Story 5.2 and the scoped onboarding layout.
  const isOnboardingRoute = pathname?.startsWith(`/${locale}/onboarding`);

  const handleLogout = async () => {
    try {
      if (session?.accessToken) {
        await fetch(`${API_URL}/api/v1/auth/logout`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session.accessToken}`,
            "Content-Type": "application/json",
          },
        });
      }
    } catch {
      // Proceed with client-side logout even if backend call fails
    }

    toast.success(t("logOutSuccess"), { duration: 4000 });
    await signOut({ callbackUrl: `/${locale}/login` });
  };

  const { isTimedOut } = useIdleTimeout({
    timeoutMs: 30 * 60 * 1000,
  });

  const handleSessionExpiredLogin = async () => {
    await signOut({ callbackUrl: `/${locale}/login` });
  };

  return (
    <AuthGuard>
      <ConsentGuard>
        <div className="min-h-screen bg-background">
          {!isOnboardingRoute && (
            <header className="border-b border-foreground/10 bg-background">
              <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
                <h1 className="text-lg font-semibold text-foreground">
                  {t("title")}
                </h1>
                <div className="flex items-center gap-2">
                  <Link
                    href="/feed"
                    className="inline-flex items-center gap-1.5 rounded-lg border border-foreground/20 px-2.5 py-1.5 text-sm text-foreground/70 hover:bg-foreground/5 hover:text-foreground transition-colors"
                    aria-label={t("feed")}
                  >
                    <BookOpen className="h-4 w-4" />
                  </Link>
                  <Link
                    href="/history"
                    className="inline-flex items-center gap-1.5 rounded-lg border border-foreground/20 px-2.5 py-1.5 text-sm text-foreground/70 hover:bg-foreground/5 hover:text-foreground transition-colors"
                    aria-label={t("history")}
                  >
                    <History className="h-4 w-4" />
                  </Link>
                  <Link
                    href="/profile"
                    className="inline-flex items-center gap-1.5 rounded-lg border border-foreground/20 px-2.5 py-1.5 text-sm text-foreground/70 hover:bg-foreground/5 hover:text-foreground transition-colors"
                    aria-label={t("profile")}
                  >
                    <User className="h-4 w-4" />
                  </Link>
                  <Link
                    href="/settings"
                    className="inline-flex items-center gap-1.5 rounded-lg border border-foreground/20 px-2.5 py-1.5 text-sm text-foreground/70 hover:bg-foreground/5 hover:text-foreground transition-colors"
                    aria-label={t("settings")}
                  >
                    <Settings className="h-4 w-4" />
                  </Link>
                  <LocaleSwitcher accessToken={session?.accessToken} />
                  <button
                    onClick={handleLogout}
                    className="rounded-lg border border-foreground/20 px-3 py-1.5 text-sm text-foreground/70 hover:bg-foreground/5 hover:text-foreground transition-colors"
                  >
                    {t("logOut")}
                  </button>
                </div>
              </div>
            </header>
          )}
          <main>{children}</main>

          {!isOnboardingRoute && (
            <Link
              href="/upload"
              className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform hover:scale-105 active:scale-95"
              aria-label={t("upload")}
            >
              <Plus className="h-6 w-6" />
            </Link>
          )}

          {!isOnboardingRoute && <AppVersionBadge />}
        </div>

        {isTimedOut && (
          <SessionExpiredDialog
            onLogin={handleSessionExpiredLogin}
          />
        )}
      </ConsentGuard>
    </AuthGuard>
  );
}
