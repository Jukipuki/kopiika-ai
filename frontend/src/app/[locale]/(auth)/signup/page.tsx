"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { Link } from "@/i18n/navigation";
import { useAuth } from "@/features/auth/hooks/use-auth";
import SignupForm from "@/features/auth/components/SignupForm";
import VerificationForm from "@/features/auth/components/VerificationForm";

export default function SignupPage() {
  const t = useTranslations("auth.signup");
  const tv = useTranslations("auth.verify");
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const locale = useLocale();
  const [step, setStep] = useState<"signup" | "verify">("signup");
  const [email, setEmail] = useState("");

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace(`/${locale}/dashboard`);
    }
  }, [isAuthenticated, isLoading, router, locale]);

  const handleSignupSuccess = (registeredEmail: string) => {
    setEmail(registeredEmail);
    setStep("verify");
  };

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
        {step === "signup" ? t("title") : tv("title")}
      </h1>

      {step === "signup" ? (
        <>
          <SignupForm onSuccess={handleSignupSuccess} />
          <p className="mt-6 text-center text-sm text-foreground/60">
            {t("hasAccount")}{" "}
            <Link href="/login" className="text-[#6C63FF] hover:underline">
              {t("logIn")}
            </Link>
          </p>
        </>
      ) : (
        <VerificationForm email={email} />
      )}
    </>
  );
}
