import { getTranslations } from "next-intl/server";
import { FeedContainer } from "@/features/teaching-feed/components/FeedContainer";

export async function generateMetadata() {
  const t = await getTranslations("feed");
  return {
    title: t("title"),
  };
}

export default function FeedPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold">Teaching Feed</h1>
      <FeedContainer />
    </div>
  );
}
