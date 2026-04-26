"use client";

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import { useTranslations } from "next-intl";
import type { CitationDto } from "../lib/chat-types";
import { renderCitationLabel } from "../lib/citation-label";
import { useLocale } from "next-intl";

interface Props {
  citation: CitationDto | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function fmtAmount(kopiykas: number, currency: string): string {
  const major = (kopiykas / 100).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${major} ${currency}`;
}

export function CitationDetailSheet({ citation, open, onOpenChange }: Props) {
  const t = useTranslations("chat");
  const locale = useLocale() as "uk" | "en";

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Backdrop className="fixed inset-0 z-50 bg-black/20 data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0" />
        <DialogPrimitive.Popup
          className="
            fixed z-50 bg-popover text-popover-foreground ring-1 ring-foreground/10
            data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0
            inset-x-0 bottom-0 rounded-t-xl p-4 max-h-[80vh] overflow-y-auto
            sm:inset-x-auto sm:bottom-auto sm:right-0 sm:top-0 sm:h-full sm:w-96 sm:rounded-l-xl sm:rounded-t-none
            motion-reduce:transition-none
          "
        >
          <DialogPrimitive.Title className="text-base font-medium">
            {t("citations.detail_title")}
          </DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            {citation ? renderCitationLabel(citation, t as never, locale) : ""}
          </DialogPrimitive.Description>

          {citation && <DetailBody citation={citation} />}

          <div className="mt-4 flex justify-end">
            <DialogPrimitive.Close className="rounded border px-3 py-1.5 text-sm hover:bg-muted">
              {t("citations.close")}
            </DialogPrimitive.Close>
          </div>
        </DialogPrimitive.Popup>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function DetailBody({ citation }: { citation: CitationDto }) {
  const t = useTranslations("chat");
  const locale = useLocale() as "uk" | "en";

  switch (citation.kind) {
    case "transaction":
      return (
        <dl className="mt-4 space-y-2 text-sm">
          <Row label={t("citations.field_date")} value={citation.bookedAt} />
          <Row label={t("citations.field_description")} value={citation.description} />
          <Row label={t("citations.field_amount")} value={fmtAmount(citation.amountKopiykas, citation.currency)} />
          <Row label={t("citations.field_category")} value={citation.categoryCode} />
          <Row label={t("citations.field_id")} value={citation.id.slice(-8)} />
          <span className="sr-only">{citation.id}</span>
        </dl>
      );
    case "category":
      return (
        <dl className="mt-4 space-y-2 text-sm">
          <Row label={t("citations.field_name")} value={renderCitationLabel(citation, t as never, locale)} />
          <Row label={t("citations.field_code")} value={citation.code} />
        </dl>
      );
    case "profile_field":
      return (
        <dl className="mt-4 space-y-2 text-sm">
          <Row label={t("citations.field_name")} value={renderCitationLabel(citation, t as never, locale)} />
          <Row
            label={t("citations.field_value")}
            value={
              typeof citation.value === "number" && citation.currency
                ? fmtAmount(citation.value, citation.currency)
                : String(citation.value ?? "")
            }
          />
          {citation.asOf && <Row label={t("citations.field_as_of")} value={citation.asOf} />}
        </dl>
      );
    case "rag_doc":
      return (
        <div className="mt-4 space-y-2 text-sm">
          <p className="font-medium">{citation.title}</p>
          <p className="text-muted-foreground">{citation.snippet.slice(0, 240)}</p>
          <p className="text-xs text-muted-foreground">
            {t("citations.similarity", { pct: Math.round(citation.similarity * 100) })}
          </p>
        </div>
      );
  }
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right">{value}</dd>
    </div>
  );
}
