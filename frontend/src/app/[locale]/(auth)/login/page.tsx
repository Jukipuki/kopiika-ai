"use client";

import { Suspense } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import LoginForm from "@/features/auth/components/LoginForm";

function LoginContent() {
  const t = useTranslations("auth.login");

  return (
    <>
      <h1 className="text-2xl font-semibold text-foreground text-center mb-6">
        {t("title")}
      </h1>

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
