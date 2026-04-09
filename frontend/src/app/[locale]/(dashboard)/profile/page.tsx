import { getTranslations } from "next-intl/server";
import { ProfilePage } from "@/features/profile/components/ProfilePage";

export async function generateMetadata() {
  const t = await getTranslations("profile");
  return {
    title: t("title"),
  };
}

export default async function ProfileRoute() {
  const t = await getTranslations("profile");

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold">{t("title")}</h1>
      <ProfilePage />
    </div>
  );
}
