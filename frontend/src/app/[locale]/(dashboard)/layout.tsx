"use client";

import { signOut, useSession } from "next-auth/react";
import { useTranslations, useLocale } from "next-intl";
import { toast } from "sonner";
import AuthGuard from "@/lib/auth/auth-guard";
import { useIdleTimeout } from "@/features/auth/hooks/use-idle-timeout";
import SessionExpiredDialog from "@/features/auth/components/SessionExpiredDialog";
import LocaleSwitcher from "@/components/layout/LocaleSwitcher";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: session } = useSession();
  const locale = useLocale();
  const t = useTranslations("dashboard");

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
      <div className="min-h-screen bg-background">
        <header className="border-b border-foreground/10 bg-background">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
            <h1 className="text-lg font-semibold text-foreground">
              {t("title")}
            </h1>
            <div className="flex items-center gap-2">
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
        <main>{children}</main>
      </div>

      {isTimedOut && (
        <SessionExpiredDialog
          onLogin={handleSessionExpiredLogin}
        />
      )}
    </AuthGuard>
  );
}
