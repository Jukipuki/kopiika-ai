"use client";

import { useState } from "react";
import { signOut, useSession } from "next-auth/react";
import { useTranslations, useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";

import { Scale } from "lucide-react";
import {
  CONSENT_TYPE_AI_PROCESSING,
  CURRENT_CONSENT_VERSION,
} from "@/features/onboarding/consent-version";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function PrivacyExplanationScreen() {
  const { data: session } = useSession();
  const t = useTranslations("onboarding.privacy");
  const te = useTranslations("errors");
  const locale = useLocale();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [isChecked, setIsChecked] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!isChecked || !session?.accessToken) return;
    setServerError(null);
    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_URL}/api/v1/users/me/consent`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          version: CURRENT_CONSENT_VERSION,
          locale,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        const message =
          errorData?.error?.message || te("serverError");
        setServerError(message);
        return;
      }

      // Invalidate the consent status cache so ConsentGuard re-reads and
      // allows the user through on the next navigation.
      await queryClient.invalidateQueries({
        queryKey: ["consent", CONSENT_TYPE_AI_PROCESSING],
      });

      router.push(`/${locale}/upload`);
    } catch {
      setServerError(te("serverError"));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = async () => {
    await signOut({ callbackUrl: `/${locale}/login` });
  };

  const topics: Array<{ titleKey: string; bodyKey: string }> = [
    { titleKey: "dataCollected.title", bodyKey: "dataCollected.body" },
    { titleKey: "aiProcessing.title", bodyKey: "aiProcessing.body" },
    { titleKey: "storage.title", bodyKey: "storage.body" },
    { titleKey: "access.title", bodyKey: "access.body" },
  ];

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6">
      <h1 className="text-2xl font-semibold text-foreground">{t("title")}</h1>
      <p className="mt-2 text-sm text-foreground/70">{t("subtitle")}</p>

      <div className="mt-8 space-y-6">
        {topics.map((topic) => (
          <section key={topic.titleKey}>
            <h2 className="text-base font-semibold text-foreground">
              {t(topic.titleKey)}
            </h2>
            <p className="mt-1 text-sm text-foreground/80 leading-relaxed">
              {t(topic.bodyKey)}
            </p>
          </section>
        ))}

        <section className="rounded-lg border border-amber-500/30 bg-amber-50/50 p-4 dark:bg-amber-950/20">
          <h2 className="flex items-center gap-2 text-base font-semibold text-foreground">
            <Scale size={18} className="text-amber-600 dark:text-amber-400" aria-hidden="true" />
            {t("disclaimer.title")}
          </h2>
          <p className="mt-1 text-sm text-foreground/80 leading-relaxed">
            {t("disclaimer.body")}
          </p>
        </section>
      </div>

      <div className="mt-8 rounded-lg border border-foreground/10 bg-foreground/[0.02] p-4">
        <label className="flex cursor-pointer items-start gap-3">
          <input
            type="checkbox"
            checked={isChecked}
            onChange={(e) => setIsChecked(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-foreground/30 accent-primary"
          />
          <span className="text-sm text-foreground leading-relaxed">
            {t("consentLabel")}
          </span>
        </label>
      </div>

      {serverError && (
        <div
          role="alert"
          className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {serverError}
        </div>
      )}

      <div className="mt-6 flex items-center justify-between">
        <button
          type="button"
          onClick={handleLogout}
          className="text-sm text-foreground/60 underline-offset-2 hover:text-foreground hover:underline"
        >
          {t("logOut")}
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!isChecked || isSubmitting}
          className="rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting ? t("submitting") : t("continue")}
        </button>
      </div>
    </div>
  );
}
