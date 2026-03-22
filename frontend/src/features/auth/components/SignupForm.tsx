"use client";

import { useState, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { type SignupFormData } from "../schemas/signup-schema";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SignupFormProps {
  onSuccess: (email: string) => void;
}

export default function SignupForm({ onSuccess }: SignupFormProps) {
  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const t = useTranslations("auth.signup");
  const tv = useTranslations("auth.validation");
  const tp = useTranslations("auth.passwordRequirements");
  const te = useTranslations("errors");

  const schema = useMemo(
    () =>
      z
        .object({
          email: z
            .string()
            .min(1, tv("emailRequired"))
            .email(tv("emailInvalid")),
          password: z
            .string()
            .min(8, tv("passwordMin"))
            .regex(/[A-Z]/, tv("passwordUppercase"))
            .regex(/[a-z]/, tv("passwordLowercase"))
            .regex(/[0-9]/, tv("passwordNumber"))
            .regex(/[^A-Za-z0-9]/, tv("passwordSpecial")),
          confirmPassword: z
            .string()
            .min(1, tv("confirmPasswordRequired")),
        })
        .refine((data) => data.password === data.confirmPassword, {
          message: tv("passwordsMismatch"),
          path: ["confirmPassword"],
        }),
    [tv]
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

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<SignupFormData>({
    resolver: zodResolver(schema),
    mode: "onBlur",
  });

  const passwordValue = watch("password", "");

  const onSubmit = async (data: SignupFormData) => {
    setServerError(null);
    setIsSubmitting(true);

    try {
      const response = await fetch(`${API_URL}/api/v1/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: data.email, password: data.password }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        const message =
          errorData?.error?.message || te("signupFailed");
        setServerError(message);
        return;
      }

      onSuccess(data.email);
    } catch {
      setServerError(te("serverError"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
      {/* Email */}
      <div>
        <label
          htmlFor="email"
          className="block text-sm font-medium text-foreground mb-1.5"
        >
          {t("email")}
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          aria-invalid={!!errors.email}
          aria-describedby={errors.email ? "email-error" : undefined}
          className={`w-full rounded-lg border px-3 py-2.5 text-sm bg-background text-foreground placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-[#6C63FF] ${
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

      {/* Password */}
      <div>
        <label
          htmlFor="password"
          className="block text-sm font-medium text-foreground mb-1.5"
        >
          {t("password")}
        </label>
        <input
          id="password"
          type="password"
          autoComplete="new-password"
          aria-invalid={!!errors.password}
          aria-describedby="password-requirements"
          className={`w-full rounded-lg border px-3 py-2.5 text-sm bg-background text-foreground placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-[#6C63FF] ${
            errors.password ? "border-[#FF6B6B]" : "border-foreground/20"
          }`}
          placeholder={t("passwordPlaceholder")}
          {...register("password")}
        />
        {/* Password requirements checklist */}
        <ul id="password-requirements" className="mt-2 space-y-1">
          {requirements.map((req) => {
            const met = req.regex.test(passwordValue);
            return (
              <li
                key={req.label}
                className={`flex items-center gap-1.5 text-xs ${
                  met ? "text-green-600 dark:text-green-400" : "text-foreground/50"
                }`}
              >
                <span>{met ? "\u2713" : "\u2022"}</span>
                {req.label}
              </li>
            );
          })}
        </ul>
      </div>

      {/* Confirm Password */}
      <div>
        <label
          htmlFor="confirmPassword"
          className="block text-sm font-medium text-foreground mb-1.5"
        >
          {t("confirmPassword")}
        </label>
        <input
          id="confirmPassword"
          type="password"
          autoComplete="new-password"
          aria-invalid={!!errors.confirmPassword}
          aria-describedby={
            errors.confirmPassword ? "confirm-password-error" : undefined
          }
          className={`w-full rounded-lg border px-3 py-2.5 text-sm bg-background text-foreground placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-[#6C63FF] ${
            errors.confirmPassword ? "border-[#FF6B6B]" : "border-foreground/20"
          }`}
          placeholder={t("confirmPasswordPlaceholder")}
          {...register("confirmPassword")}
        />
        {errors.confirmPassword && (
          <p id="confirm-password-error" className="mt-1 text-sm text-[#FF6B6B]">
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
        className="w-full rounded-lg bg-[#6C63FF] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#5B54E6] focus:outline-none focus:ring-2 focus:ring-[#6C63FF] focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isSubmitting ? t("submitting") : t("submit")}
      </button>
    </form>
  );
}
