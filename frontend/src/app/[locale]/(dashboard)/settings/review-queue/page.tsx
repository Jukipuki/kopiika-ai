import { getTranslations } from "next-intl/server";
import ReviewQueuePage from "@/features/review-queue/components/ReviewQueuePage";
import FeatureErrorBoundary from "@/components/error/FeatureErrorBoundary";

export async function generateMetadata() {
  const t = await getTranslations("settings.reviewQueue");
  return {
    title: t("pageTitle"),
  };
}

export default function ReviewQueueRoute() {
  return (
    <FeatureErrorBoundary feature="review-queue">
      <ReviewQueuePage />
    </FeatureErrorBoundary>
  );
}
