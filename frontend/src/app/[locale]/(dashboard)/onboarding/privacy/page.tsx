import { getTranslations } from "next-intl/server";
import PrivacyExplanationScreen from "@/features/onboarding/components/PrivacyExplanationScreen";

export async function generateMetadata() {
  const t = await getTranslations("onboarding.privacy");
  return {
    title: t("title"),
  };
}

export default function PrivacyOnboardingRoute() {
  return <PrivacyExplanationScreen />;
}
