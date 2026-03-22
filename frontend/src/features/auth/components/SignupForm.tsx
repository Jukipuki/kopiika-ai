"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  signupSchema,
  type SignupFormData,
  passwordRequirements,
} from "../schemas/signup-schema";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SignupFormProps {
  onSuccess: (email: string) => void;
}

export default function SignupForm({ onSuccess }: SignupFormProps) {
  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<SignupFormData>({
    resolver: zodResolver(signupSchema),
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
          errorData?.error?.message || "An unexpected error occurred";
        setServerError(message);
        return;
      }

      onSuccess(data.email);
    } catch {
      setServerError("Unable to connect to the server. Please try again.");
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
          {/* i18n: auth.signup.email */}
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
          {/* i18n: auth.signup.password */}
          Password
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
          placeholder="Create a password"
          {...register("password")}
        />
        {/* Password requirements checklist */}
        <ul id="password-requirements" className="mt-2 space-y-1">
          {passwordRequirements.map((req) => {
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
          {/* i18n: auth.signup.confirmPassword */}
          Confirm Password
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
          placeholder="Confirm your password"
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
        {/* i18n: auth.signup.submit */}
        {isSubmitting ? "Creating account..." : "Create Account"}
      </button>
    </form>
  );
}
