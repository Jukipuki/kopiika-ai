"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import SignupForm from "@/features/auth/components/SignupForm";
import VerificationForm from "@/features/auth/components/VerificationForm";

export default function SignupPage() {
  const t = useTranslations("auth.signup");
  const tv = useTranslations("auth.verify");
  const [step, setStep] = useState<"signup" | "verify">("signup");
  const [email, setEmail] = useState("");

  const handleSignupSuccess = (registeredEmail: string) => {
    setEmail(registeredEmail);
    setStep("verify");
  };

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
