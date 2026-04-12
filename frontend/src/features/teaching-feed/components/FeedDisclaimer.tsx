"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Info } from "lucide-react";

export function FeedDisclaimer() {
  const t = useTranslations("feed.disclaimer");
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="flex items-start gap-2 rounded-lg border border-foreground/10 bg-foreground/[0.02] px-3 py-2" data-testid="feed-disclaimer">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="mt-0.5 flex-shrink-0 text-muted-foreground hover:text-foreground"
        aria-expanded={isExpanded}
        aria-label={t("toggleLabel")}
      >
        <Info size={16} />
      </button>
      <div className="text-xs text-muted-foreground leading-relaxed">
        <p>{t("short")}</p>
        {isExpanded && (
          <p className="mt-1 text-foreground/60">{t("full")}</p>
        )}
      </div>
    </div>
  );
}
