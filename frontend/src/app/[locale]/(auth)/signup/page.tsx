"use client";

import { useState } from "react";
import SignupForm from "@/features/auth/components/SignupForm";
import VerificationForm from "@/features/auth/components/VerificationForm";

export default function SignupPage() {
  const [step, setStep] = useState<"signup" | "verify">("signup");
  const [email, setEmail] = useState("");

  const handleSignupSuccess = (registeredEmail: string) => {
    setEmail(registeredEmail);
    setStep("verify");
  };

  return (
    <>
      <h1 className="text-2xl font-semibold text-foreground text-center mb-6">
        {step === "signup"
          ? /* i18n: auth.signup.title */ "Create your account"
          : /* i18n: auth.verify.title */ "Verify your email"}
      </h1>

      {step === "signup" ? (
        <SignupForm onSuccess={handleSignupSuccess} />
      ) : (
        <VerificationForm email={email} />
      )}
    </>
  );
}
