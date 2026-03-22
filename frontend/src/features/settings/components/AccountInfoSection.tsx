"use client";

import { useTranslations, useLocale } from "next-intl";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { formatDateLong } from "@/lib/format/date";
import type { UserProfile } from "../hooks/use-user-profile";

interface AccountInfoSectionProps {
  profile: UserProfile;
}

export default function AccountInfoSection({ profile }: AccountInfoSectionProps) {
  const t = useTranslations("settings");
  const locale = useLocale();

  return (
    <section aria-labelledby="account-info-heading">
      <Card>
        <CardHeader>
          <h2 id="account-info-heading" className="text-lg font-medium leading-snug">
            {t("accountInfo")}
          </h2>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-1">
            <span className="text-sm text-muted-foreground">{t("email")}</span>
            <div className="flex items-center gap-2">
              <p aria-label={t("email")}>{profile.email}</p>
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                  profile.isVerified
                    ? "bg-green-500/10 text-green-500"
                    : "bg-yellow-500/10 text-yellow-500"
                }`}
                aria-label={profile.isVerified ? t("emailVerified") : t("emailNotVerified")}
              >
                {profile.isVerified ? t("emailVerified") : t("emailNotVerified")}
              </span>
            </div>
          </div>

          <Separator />

          <div className="flex flex-col gap-1">
            <span className="text-sm text-muted-foreground">{t("memberSince")}</span>
            <p>{formatDateLong(profile.createdAt, locale)}</p>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
