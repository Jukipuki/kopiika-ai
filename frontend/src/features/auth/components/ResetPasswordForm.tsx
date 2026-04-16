"use client";

import { useState, useMemo, useCallback } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/i18n/navigation";
import { z } from "zod";
import { type ResetPasswordFormData } from "../schemas/reset-password-schema";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const emailFromParams = searchParams.get("email") || "";

  const t = useTranslations("auth.resetPassword");
  const tf = useTranslations("auth.forgotPassword");
  const tv = useTranslations("auth.validation");
  const tp = useTranslations("auth.passwordRequirements");
  const te = useTranslations("errors");

  const schema = useMemo(
    () =>
      z
        .object({
          code: z.string().length(6, tv("codeInvalid")),
          newPassword: z
            .string()
            .min(8, tv("passwordMin"))
            .regex(/[A-Z]/, tv("passwordUppercase"))
            .regex(/[a-z]/, tv("passwordLowercase"))
            .regex(/[0-9]/, tv("passwordNumber"))
            .regex(/[^A-Za-z0-9]/, tv("passwordSpecial")),
          confirmPassword: z.string().min(1, tv("confirmPasswordRequired")),
        })
        .refine((data) => data.newPassword === data.confirmPassword, {
          message: t("passwordMismatch"),
          path: ["confirmPassword"],
        }),
    [t, tv]
  );

  const requirements = useMemo(
    () => [
      { label: tp("minLength"), regex: /.{8,}/ },
      { label: tp("uppercase"), regex: /[A-Z]/ },
      { label: tp("lowercase"), regex: /[a-z]/ },
      { label: tp("number"), regex: /[0-9]/ },
      { label: tp("special"), regex: /[^A-Za-z0-9]/ },
    ],
    [tp]
  );

  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<ResetPasswordFormData>({
    resolver: zodResolver(schema),
    mode: "onBlur",
    defaultValues: { code: "", newPassword: "", confirmPassword: "" },
  });

  const codeValue = watch("code", "");
  const passwordValue = watch("newPassword", "");

  const onSubmit = useCallback(
    async (data: ResetPasswordFormData) => {
      setServerError(null);
      setIsSubmitting(true);

      try {
        const response = await fetch(
          `${API_URL}/api/v1/auth/reset-password`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: emailFromParams,
              code: data.code,
              newPassword: data.newPassword,
            }),
          }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => null);
          const errorCode = errorData?.error?.code;

          if (
            errorCode === "RESET_CODE_INVALID" ||
            errorCode === "RESET_CODE_EXPIRED"
          ) {
            setServerError(t("invalidCode"));
          } else if (errorCode === "PASSWORD_TOO_WEAK") {
            setServerError(
              errorData?.error?.message || tv("passwordMin")
            );
          } else if (errorCode === "RATE_LIMITED") {
            setServerError(te("rateLimited", { minutes: 15 }));
          } else {
            setServerError(
              errorData?.error?.message || te("serverError")
            );
          }
          return;
        }

        router.push("/login?reset=success");
      } catch {
        setServerError(te("serverError"));
      } finally {
        setIsSubmitting(false);
      }
    },
    [emailFromParams, router, t, te, tv]
  );

  if (!emailFromParams) {
    return (
      <div className="space-y-5 text-center">
        <div
          role="alert"
          className="rounded-lg bg-[#FF6B6B]/10 border border-[#FF6B6B]/30 px-3 py-2 text-sm text-[#FF6B6B]"
        >
          {t("invalidCode")}
        </div>
        <Link
          href="/forgot-password"
          className="inline-flex min-h-[44px] w-full items-center justify-center rounded-lg bg-[#6C63FF] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#5B54E6] focus:outline-none focus:ring-2 focus:ring-[#6C63FF] focus:ring-offset-2 transition-colors"
        >
          {t("backToForgotPassword")}
        </Link>
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
        {tf("confirmationMessage")}{" "}
        <span className="font-medium text-foreground">{emailFromParams}</span>
      </p>

      {/* Reset code */}
      <div>
        <label
          htmlFor="code"
          className="block text-sm font-medium text-foreground mb-1.5"
        >
          {t("codeLabel")}
        </label>
        <input
          id="code"
          type="text"
          inputMode="numeric"
          maxLength={6}
          pattern="[0-9]{6}"
          autoComplete="one-time-code"
          aria-invalid={!!errors.code}
          aria-describedby={errors.code ? "code-error" : undefined}
          value={codeValue}
          onChange={(e) => {
            const val = e.target.value.replace(/\D/g, "").slice(0, 6);
            setValue("code", val, { shouldValidate: true });
          }}
          className={`w-full min-h-[44px] rounded-lg border px-3 py-2.5 text-center text-lg tracking-[0.5em] font-mono bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-[#6C63FF] ${
            errors.code ? "border-[#FF6B6B]" : "border-foreground/20"
          }`}
          placeholder={t("codePlaceholder")}
        />
        {errors.code && (
          <p id="code-error" className="mt-1 text-sm text-[#FF6B6B]">
            {errors.code.message}
          </p>
        )}
      </div>

      {/* New password */}
      <div>
        <label
          htmlFor="newPassword"
          className="block text-sm font-medium text-foreground mb-1.5"
        >
          {t("newPasswordLabel")}
        </label>
        <input
          id="newPassword"
          type="password"
          autoComplete="new-password"
          aria-invalid={!!errors.newPassword}
          aria-describedby="reset-password-requirements"
          className={`w-full min-h-[44px] rounded-lg border px-3 py-2.5 text-sm bg-background text-foreground placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-[#6C63FF] ${
            errors.newPassword ? "border-[#FF6B6B]" : "border-foreground/20"
          }`}
          {...register("newPassword")}
        />
        <ul
          id="reset-password-requirements"
          className="mt-2 space-y-1"
        >
          {requirements.map((req) => {
            const met = req.regex.test(passwordValue);
            return (
              <li
                key={req.label}
                className={`flex items-center gap-1.5 text-xs ${
                  met
                    ? "text-green-600 dark:text-green-400"
                    : "text-foreground/50"
                }`}
              >
                <span>{met ? "\u2713" : "\u2022"}</span>
                {req.label}
              </li>
            );
          })}
        </ul>
      </div>

      {/* Confirm new password */}
      <div>
        <label
          htmlFor="confirmPassword"
          className="block text-sm font-medium text-foreground mb-1.5"
        >
          {t("confirmPasswordLabel")}
        </label>
        <input
          id="confirmPassword"
          type="password"
          autoComplete="new-password"
          aria-invalid={!!errors.confirmPassword}
          aria-describedby={
            errors.confirmPassword ? "confirm-password-error" : undefined
          }
          className={`w-full min-h-[44px] rounded-lg border px-3 py-2.5 text-sm bg-background text-foreground placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-[#6C63FF] ${
            errors.confirmPassword
              ? "border-[#FF6B6B]"
              : "border-foreground/20"
          }`}
          {...register("confirmPassword")}
        />
        {errors.confirmPassword && (
          <p
            id="confirm-password-error"
            className="mt-1 text-sm text-[#FF6B6B]"
          >
            {errors.confirmPassword.message}
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
          href="/forgot-password"
          className="text-sm text-[#6C63FF] hover:underline"
        >
          {t("backToForgotPassword")}
        </Link>
      </div>
    </form>
  );
}
