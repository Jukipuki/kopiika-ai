"use client";

import { Suspense } from "react";
import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { Link } from "@/i18n/navigation";
import { useAuth } from "@/features/auth/hooks/use-auth";
import LoginForm from "@/features/auth/components/LoginForm";

function LoginContent() {
  const t = useTranslations("auth.login");
  const tr = useTranslations("auth.resetPassword");
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const locale = useLocale();
  const resetSuccess = searchParams.get("reset") === "success";

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace(`/${locale}/dashboard`);
    }
  }, [isAuthenticated, isLoading, router, locale]);

  if (isLoading || isAuthenticated) {
    return (
      <div className="flex min-h-[200px] items-center justify-center">
        <div className="text-foreground/50 text-sm">Loading...</div>
      </div>
    );
  }

  return (
    <>
      <h1 className="text-2xl font-semibold text-foreground text-center mb-6">
        {t("title")}
      </h1>

      {resetSuccess && (
        <div
          role="status"
          className="mb-4 rounded-lg border border-green-600/30 bg-green-600/10 px-3 py-2 text-sm text-green-700 dark:text-green-400"
        >
          {tr("successBanner")}
        </div>
      )}

      <LoginForm />

      <p className="mt-6 text-center text-sm text-foreground/60">
        {t("noAccount")}{" "}
        <Link href="/signup" className="text-[#6C63FF] hover:underline">
          {t("signUp")}
        </Link>
      </p>
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[200px] items-center justify-center">
          <div className="text-foreground/50 text-sm">Loading...</div>
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}
