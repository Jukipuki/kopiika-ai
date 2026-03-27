import { getTranslations } from "next-intl/server";
import UploadDropzone from "@/features/upload/components/UploadDropzone";

export async function generateMetadata() {
  const t = await getTranslations("upload");
  return {
    title: t("title"),
  };
}

export default function UploadRoute() {
  return (
    <main className="px-4 py-6 md:mx-auto md:max-w-2xl md:px-6 lg:max-w-3xl">
      <UploadDropzone />
    </main>
  );
}
