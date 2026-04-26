import { getLocale, getTranslations } from "next-intl/server";
import FeatureErrorBoundary from "@/components/error/FeatureErrorBoundary";
import { ChatScreen } from "@/features/chat";

export async function generateMetadata() {
  const t = await getTranslations("chat");
  return { title: t("page_title") };
}

export default async function ChatRoute() {
  const locale = await getLocale();
  return (
    <FeatureErrorBoundary feature="chat">
      <ChatScreen privacyHref={`/${locale}/settings`} />
    </FeatureErrorBoundary>
  );
}
