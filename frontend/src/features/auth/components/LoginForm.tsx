"use client";

import { useState, useEffect, useCallback } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { loginSchema, type LoginFormData } from "../schemas/login-schema";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") || "/en/dashboard";

  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [rateLimitSeconds, setRateLimitSeconds] = useState(0);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
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
            setServerError(
              `Too many login attempts. Please try again in ${minutes} minute${minutes !== 1 ? "s" : ""}.`
            );
          } else if (errorCode === "EMAIL_NOT_VERIFIED") {
            setServerError(
              "Please verify your email before logging in. Check your inbox for the verification link."
            );
          } else {
            setServerError(
              errorData?.error?.message || "Invalid email or password."
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
          setServerError("Login failed. Please try again.");
          return;
        }

        router.push(callbackUrl);
      } catch {
        setServerError("Unable to connect to the server. Please try again.");
      } finally {
        setIsSubmitting(false);
      }
    },
    [callbackUrl, router]
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
          Email
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
          placeholder="you@example.com"
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
          Password
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
          placeholder="Enter your password"
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
        <a
          href="/forgot-password"
          className="text-sm text-[#6C63FF] hover:underline"
        >
          Forgot password?
        </a>
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
          ? "Signing in..."
          : isRateLimited
            ? `Try again in ${Math.ceil(rateLimitSeconds / 60)}m ${rateLimitSeconds % 60}s`
            : "Sign In"}
      </button>
    </form>
  );
}
