"use client";

import { useState } from "react";
import { Receipt, Book } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { CitationDto } from "../lib/chat-types";
import { renderCitationLabel } from "../lib/citation-label";
import { CitationDetailSheet } from "./CitationDetailSheet";

interface Props {
  citations: CitationDto[];
}

export function CitationChipRow({ citations }: Props) {
  const t = useTranslations("chat");
  const locale = useLocale() as "uk" | "en";
  const [active, setActive] = useState<CitationDto | null>(null);

  if (!citations || citations.length === 0) return null;

  return (
    <>
      <div
        role="list"
        aria-label={t("citations.row_label")}
        className="mt-2 flex max-w-full gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {citations.map((c, i) => {
          const knownKind = c.kind === "transaction" || c.kind === "category" || c.kind === "profile_field" || c.kind === "rag_doc";
          if (!knownKind) {
            console.warn("[chat-citations] unknown citation kind, skipped", c);
            return null;
          }
          const Icon = c.kind === "rag_doc" ? Book : Receipt;
          const label = renderCitationLabel(c, t as never, locale);
          return (
            <button
              key={`${c.kind}-${i}`}
              type="button"
              role="listitem"
              onClick={() => setActive(c)}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs hover:bg-muted/80 focus-visible:outline-2 focus-visible:outline-ring max-w-[16rem]"
              title={label}
            >
              <Icon aria-hidden="true" className="h-3 w-3" />
              <span className="truncate">{label}</span>
            </button>
          );
        })}
      </div>
      <CitationDetailSheet
        citation={active}
        open={active !== null}
        onOpenChange={(o) => !o && setActive(null)}
      />
    </>
  );
}
