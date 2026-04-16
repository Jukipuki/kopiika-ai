"use client";

import { useState, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { z } from "zod";
import { type ForgotPasswordFormData } from "../schemas/forgot-password-schema";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ForgotPasswordForm() {
  const t = useTranslations("auth.forgotPassword");
  const tv = useTranslations("auth.validation");
  const te = useTranslations("errors");

  const schema = useMemo(
    () =>
      z.object({
        email: z.string().min(1, tv("emailRequired")).email(tv("emailInvalid")),
      }),
    [tv]
  );

  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordFormData>({
    resolver: zodResolver(schema),
    mode: "onBlur",
  });

  const onSubmit = async (data: ForgotPasswordFormData) => {
    setServerError(null);
    setIsSubmitting(true);

    try {
      const response = await fetch(
        `${API_URL}/api/v1/auth/forgot-password`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: data.email }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        const errorCode = errorData?.error?.code;

        if (errorCode === "USER_NOT_CONFIRMED") {
          setServerError(te("emailNotVerified"));
        } else if (errorCode === "RATE_LIMITED") {
          setServerError(te("rateLimited", { minutes: 15 }));
        } else {
          setServerError(
            errorData?.error?.message || te("serverError")
          );
        }
        return;
      }

      setSubmittedEmail(data.email);
    } catch {
      setServerError(te("serverError"));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (submittedEmail) {
    return (
      <div className="space-y-5 text-center">
        <div className="text-4xl" aria-hidden="true">
          {"\u2709\uFE0F"}
        </div>
        <h2 className="text-xl font-semibold text-foreground">
          {t("confirmationTitle")}
        </h2>
        <p className="text-sm text-foreground/70">
          {t("confirmationMessage")}
        </p>
        <p className="text-sm font-medium text-foreground">
          {submittedEmail}
        </p>
        <Link
          href={{
            pathname: "/forgot-password/confirm",
            query: { email: submittedEmail },
          }}
          className="inline-flex min-h-[44px] w-full items-center justify-center rounded-lg bg-[#6C63FF] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#5B54E6] focus:outline-none focus:ring-2 focus:ring-[#6C63FF] focus:ring-offset-2 transition-colors"
        >
          {t("enterCode")}
        </Link>
        <div className="text-sm text-foreground/60">
          {t("noCodeReceived")}{" "}
          <button
            type="button"
            onClick={() => setSubmittedEmail(null)}
            className="text-[#6C63FF] hover:underline"
          >
            {t("tryAgain")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      method="POST"
      className="space-y-5"
      noValidate
    >
      <p className="text-sm text-foreground/60 text-center">
        {t("description")}
      </p>

      {/* Email */}
      <div>
        <label
          htmlFor="email"
          className="block text-sm font-medium text-foreground mb-1.5"
        >
          {t("emailLabel")}
        </label>
        <input
          id="email"
          type="email"
          inputMode="email"
          autoComplete="email"
          aria-invalid={!!errors.email}
          aria-describedby={errors.email ? "email-error" : undefined}
          className={`w-full min-h-[44px] rounded-lg border px-3 py-2.5 text-sm bg-background text-foreground placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-[#6C63FF] ${
            errors.email ? "border-[#FF6B6B]" : "border-foreground/20"
          }`}
          placeholder={t("emailPlaceholder")}
          {...register("email")}
        />
        {errors.email && (
          <p id="email-error" className="mt-1 text-sm text-[#FF6B6B]">
            {errors.email.message}
          </p>
        )}
      </div>

      {/* Server Error */}
      {serverError && (
        <div
          role="alert"
          className="rounded-lg bg-[#FF6B6B]/10 border border-[#FF6B6B]/30 px-3 py-2 text-sm text-[#FF6B6B]"
        >
          {serverError}
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full min-h-[44px] rounded-lg bg-[#6C63FF] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#5B54E6] focus:outline-none focus:ring-2 focus:ring-[#6C63FF] focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isSubmitting ? t("submitting") : t("submit")}
      </button>

      <div className="text-center">
        <Link
          href="/login"
          className="text-sm text-[#6C63FF] hover:underline"
        >
          {t("backToLogin")}
        </Link>
      </div>
    </form>
  );
}
