import { getTranslations } from "next-intl/server";
import UploadHistoryList from "@/features/upload/components/UploadHistoryList";

export async function generateMetadata() {
  const t = await getTranslations("history");
  return {
    title: t("title"),
  };
}

export default function HistoryRoute() {
  return (
    <main className="px-4 py-6 md:mx-auto md:max-w-2xl md:px-6 lg:max-w-3xl">
      <UploadHistoryList />
    </main>
  );
}
