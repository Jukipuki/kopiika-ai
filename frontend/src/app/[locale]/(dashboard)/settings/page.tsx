import { getTranslations } from "next-intl/server";
import SettingsPage from "@/features/settings/components/SettingsPage";

export async function generateMetadata() {
  const t = await getTranslations("settings");
  return {
    title: t("title"),
  };
}

export default function SettingsRoute() {
  return <SettingsPage />;
}
