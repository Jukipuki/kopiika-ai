"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const RESEND_COOLDOWN = 60; // seconds

interface VerificationFormProps {
  email: string;
}

export default function VerificationForm({ email }: VerificationFormProps) {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isVerified, setIsVerified] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (isVerified) {
      const timer = setTimeout(() => {
        router.push("/en/login");
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [isVerified, router]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => {
      setCooldown((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  const handleVerify = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (code.length !== 6) {
        setError("Please enter a 6-digit verification code");
        return;
      }

      setError(null);
      setIsSubmitting(true);

      try {
        const response = await fetch(`${API_URL}/api/v1/auth/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, code }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          setError(
            errorData?.error?.message || "Verification failed. Please try again."
          );
          return;
        }

        setIsVerified(true);
      } catch {
        setError("Unable to connect to the server. Please try again.");
      } finally {
        setIsSubmitting(false);
      }
    },
    [code, email]
  );

  const handleResend = async () => {
    if (cooldown > 0) return;

    try {
      const response = await fetch(
        `${API_URL}/api/v1/auth/resend-verification`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        }
      );

      if (response.ok) {
        setCooldown(RESEND_COOLDOWN);
      }
    } catch {
      // Silently fail — user can retry
    }
  };

  if (isVerified) {
    return (
      <div className="text-center space-y-4">
        <div className="text-4xl">&#x2705;</div>
        <h2 className="text-xl font-semibold text-foreground">
          {/* i18n: auth.verify.success.title */}
          Email Verified
        </h2>
        <p className="text-sm text-foreground/60">
          {/* i18n: auth.verify.success.message */}
          Your account has been verified. Redirecting to login...
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleVerify} className="space-y-5">
      <p className="text-sm text-foreground/60 text-center">
        {/* i18n: auth.verify.instructions */}
        We sent a verification code to{" "}
        <span className="font-medium text-foreground">{email}</span>
      </p>

      <div>
        <label
          htmlFor="code"
          className="block text-sm font-medium text-foreground mb-1.5"
        >
          {/* i18n: auth.verify.code */}
          Verification Code
        </label>
        <input
          id="code"
          type="text"
          inputMode="numeric"
          maxLength={6}
          pattern="[0-9]{6}"
          autoComplete="one-time-code"
          aria-invalid={!!error}
          aria-describedby={error ? "code-error" : undefined}
          value={code}
          onChange={(e) => {
            const val = e.target.value.replace(/\D/g, "").slice(0, 6);
            setCode(val);
          }}
          className={`w-full rounded-lg border px-3 py-2.5 text-center text-lg tracking-[0.5em] font-mono bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-[#6C63FF] ${
            error ? "border-[#FF6B6B]" : "border-foreground/20"
          }`}
          placeholder="000000"
        />
        {error && (
          <p id="code-error" className="mt-1 text-sm text-[#FF6B6B]">
            {error}
          </p>
        )}
      </div>

      <button
        type="submit"
        disabled={isSubmitting || code.length !== 6}
        className="w-full rounded-lg bg-[#6C63FF] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#5B54E6] focus:outline-none focus:ring-2 focus:ring-[#6C63FF] focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {/* i18n: auth.verify.submit */}
        {isSubmitting ? "Verifying..." : "Verify Email"}
      </button>

      <div className="text-center">
        <button
          type="button"
          onClick={handleResend}
          disabled={cooldown > 0}
          className="text-sm text-[#6C63FF] hover:underline disabled:text-foreground/40 disabled:no-underline disabled:cursor-not-allowed"
        >
          {cooldown > 0
            ? /* i18n: auth.verify.resendCooldown */ `Resend code in ${cooldown}s`
            : /* i18n: auth.verify.resend */ "Resend verification code"}
        </button>
      </div>
    </form>
  );
}
