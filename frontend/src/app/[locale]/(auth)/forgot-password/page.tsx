"use client";

import { Suspense, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { useAuth } from "@/features/auth/hooks/use-auth";
import ForgotPasswordForm from "@/features/auth/components/ForgotPasswordForm";

function ForgotPasswordContent() {
  const t = useTranslations("auth.forgotPassword");
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const locale = useLocale();

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
      <ForgotPasswordForm />
    </>
  );
}

export default function ForgotPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[200px] items-center justify-center">
          <div className="text-foreground/50 text-sm">Loading...</div>
        </div>
      }
    >
      <ForgotPasswordContent />
    </Suspense>
  );
}
