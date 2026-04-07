import { getTranslations } from "next-intl/server";
import { FeedContainer } from "@/features/teaching-feed/components/FeedContainer";

export async function generateMetadata() {
  const t = await getTranslations("feed");
  return {
    title: t("title"),
  };
}

export default async function FeedPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const t = await getTranslations("feed");
  const { jobId } = await searchParams;
  const jobIdStr = typeof jobId === "string" ? jobId : undefined;

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold">{t("title")}</h1>
      <FeedContainer jobId={jobIdStr} />
    </div>
  );
}
