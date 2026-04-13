import { getTranslations } from "next-intl/server";
import SettingsPage from "@/features/settings/components/SettingsPage";
import FeatureErrorBoundary from "@/components/error/FeatureErrorBoundary";

export async function generateMetadata() {
  const t = await getTranslations("settings");
  return {
    title: t("title"),
  };
}

export default function SettingsRoute() {
  return (
    <FeatureErrorBoundary feature="settings">
      <SettingsPage />
    </FeatureErrorBoundary>
  );
}
