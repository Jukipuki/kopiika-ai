"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { Link } from "@/i18n/navigation";
import { z } from "zod";
import { type LoginFormData } from "../schemas/login-schema";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const locale = useLocale();
  const callbackUrl = searchParams.get("callbackUrl") || `/${locale}/dashboard`;
  const t = useTranslations("auth.login");
  const tv = useTranslations("auth.validation");
  const te = useTranslations("errors");

  const schema = useMemo(
    () =>
      z.object({
        email: z.string().min(1, tv("emailRequired")).email(tv("emailInvalid")),
        password: z.string().min(1, tv("passwordRequired")),
      }),
    [tv]
  );

  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [rateLimitSeconds, setRateLimitSeconds] = useState(0);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(schema),
    mode: "onBlur",
  });

  useEffect(() => {
    if (rateLimitSeconds <= 0) return;
    const timer = setInterval(() => {
      setRateLimitSeconds((prev) => {
        if (prev <= 1) return 0;
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [rateLimitSeconds]);

  const onSubmit = useCallback(
    async (data: LoginFormData) => {
      setServerError(null);
      setIsSubmitting(true);

      try {
        const response = await fetch(`${API_URL}/api/v1/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: data.email, password: data.password }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          const errorCode = errorData?.error?.code;

          if (errorCode === "RATE_LIMITED") {
            const retryAfter =
              errorData?.error?.details?.retryAfter ||
              parseInt(response.headers.get("Retry-After") || "900", 10);
            const minutes = Math.ceil(retryAfter / 60);
            setRateLimitSeconds(retryAfter);
            setServerError(te("rateLimited", { minutes }));
          } else if (errorCode === "EMAIL_NOT_VERIFIED") {
            setServerError(te("emailNotVerified"));
          } else {
            setServerError(
              errorData?.error?.message || te("invalidCredentials")
            );
          }
          return;
        }

        const loginData = await response.json();

        const result = await signIn("credentials", {
          redirect: false,
          accessToken: loginData.accessToken,
          refreshToken: loginData.refreshToken,
          expiresIn: loginData.expiresIn,
          userId: loginData.user.id,
          email: loginData.user.email,
          locale: loginData.user.locale,
        });

        if (result?.error) {
          setServerError(te("loginFailed"));
          return;
        }

        router.push(callbackUrl);
      } catch {
        setServerError(te("serverError"));
      } finally {
        setIsSubmitting(false);
      }
    },
    [callbackUrl, router, te]
  );

  const isRateLimited = rateLimitSeconds > 0;

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
          autoComplete="current-password"
          aria-invalid={!!errors.password}
          aria-describedby={errors.password ? "password-error" : undefined}
          className={`w-full rounded-lg border px-3 py-2.5 text-sm bg-background text-foreground placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-[#6C63FF] ${
            errors.password ? "border-[#FF6B6B]" : "border-foreground/20"
          }`}
          placeholder={t("passwordPlaceholder")}
          {...register("password")}
        />
        {errors.password && (
          <p id="password-error" className="mt-1 text-sm text-[#FF6B6B]">
            {errors.password.message}
          </p>
        )}
      </div>

      {/* Forgot password link */}
      <div className="text-right">
        <Link
          href="/forgot-password"
          className="text-sm text-[#6C63FF] hover:underline"
        >
          {t("forgotPassword")}
        </Link>
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
        disabled={isSubmitting || isRateLimited}
        className="w-full rounded-lg bg-[#6C63FF] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#5B54E6] focus:outline-none focus:ring-2 focus:ring-[#6C63FF] focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isSubmitting
          ? t("submitting")
          : isRateLimited
            ? te("rateLimitTimer", {
                minutes: Math.ceil(rateLimitSeconds / 60),
                seconds: rateLimitSeconds % 60,
              })
            : t("submit")}
      </button>
    </form>
  );
}
