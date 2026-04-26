"use client";

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

interface Props {
  open: boolean;
  onAccept: () => void;
  onDecline: () => void;
  privacyHref: string;
}

export function ConsentFirstUseDialog({ open, onAccept, onDecline, privacyHref }: Props) {
  const t = useTranslations("chat");
  const router = useRouter();

  const handleDecline = () => {
    onDecline();
    router.back();
  };

  return (
    <DialogPrimitive.Root
      open={open}
      onOpenChange={(o) => {
        if (!o) handleDecline();
      }}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Backdrop className="fixed inset-0 z-50 bg-black/30 data-open:animate-in data-open:fade-in-0" />
        <DialogPrimitive.Popup className="fixed inset-x-0 bottom-0 z-50 max-h-[80vh] overflow-y-auto rounded-t-xl bg-popover p-5 ring-1 ring-foreground/10 sm:bottom-auto sm:left-1/2 sm:top-1/2 sm:max-w-md sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-xl data-open:animate-in data-open:fade-in-0 motion-reduce:transition-none">
          <DialogPrimitive.Title className="text-lg font-semibold">
            {t("consent.first_use.title")}
          </DialogPrimitive.Title>
          <DialogPrimitive.Description className="mt-2 text-sm text-muted-foreground whitespace-pre-line">
            {t("consent.first_use.body")}
          </DialogPrimitive.Description>
          <a
            href={privacyHref}
            className="mt-3 inline-block text-sm underline hover:text-foreground"
          >
            {t("consent.first_use.privacy_link")}
          </a>
          <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <DialogPrimitive.Close
              render={<Button variant="outline" onClick={handleDecline} />}
            >
              {t("consent.first_use.decline")}
            </DialogPrimitive.Close>
            <Button onClick={onAccept}>{t("consent.first_use.accept")}</Button>
          </div>
        </DialogPrimitive.Popup>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
