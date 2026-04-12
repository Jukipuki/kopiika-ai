"use client";

import { useTranslations } from "next-intl";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useUserProfile } from "../hooks/use-user-profile";
import AccountInfoSection from "./AccountInfoSection";
import LanguageSection from "./LanguageSection";
import MyDataSection from "./MyDataSection";

export default function SettingsPage() {
  const t = useTranslations("settings");
  const tErrors = useTranslations("errors");
  const { profile, isLoading, error, refetch } = useUserProfile();

  if (isLoading) {
    return (
      <main className="px-4 py-6 md:mx-auto md:max-w-2xl md:px-6 lg:max-w-3xl">
        <Skeleton className="mb-6 h-8 w-48" />
        <div className="space-y-6">
          <Skeleton className="h-40 w-full rounded-xl" />
          <Skeleton className="h-32 w-full rounded-xl" />
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="px-4 py-6 md:mx-auto md:max-w-2xl md:px-6 lg:max-w-3xl">
        <h1 className="mb-6 text-2xl font-semibold">{t("title")}</h1>
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-8">
            <p className="text-muted-foreground">{tErrors("serverError")}</p>
            <Button
              onClick={refetch}
              className="min-h-[44px] min-w-[44px]"
            >
              {tErrors("retry")}
            </Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <main className="px-4 py-6 md:mx-auto md:max-w-2xl md:px-6 lg:max-w-3xl">
      <h1 className="mb-6 text-2xl font-semibold">{t("title")}</h1>
      <div className="space-y-6">
        {profile && <AccountInfoSection profile={profile} />}
        <LanguageSection />
        <MyDataSection />
      </div>
    </main>
  );
}
