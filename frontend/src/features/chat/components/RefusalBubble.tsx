"use client";

import { useState } from "react";
import { Info, Copy as CopyIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { refusalCopyKey } from "../lib/refusal-copy";
import { RateLimitCountdown } from "./RateLimitCountdown";
import type { ChatTurnState } from "../hooks/useChatStream";

interface Props {
  turn: ChatTurnState;
  onRetry?: () => void;
}

function formatHm(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function nowLocalHm(): string {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + 1);
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function RefusalBubble({ turn, onRetry }: Props) {
  const t = useTranslations("chat");
  const [copied, setCopied] = useState(false);
  const [elapsed, setElapsed] = useState(false);
  const refusal = turn.refusal!;
  const correlationShort = refusal.correlationId.slice(0, 8);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(refusal.correlationId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Insecure-context fallback per AC #7: select-and-instruct.
      const sel = window.getSelection();
      const range = document.createRange();
      const node = document.getElementById(`chat-corr-${turn.id}`);
      if (node && sel) {
        range.selectNodeContents(node);
        sel.removeAllRanges();
        sel.addRange(range);
      }
      window.alert(t("refusal.copy_fallback_hint"));
    }
  };

  const time = formatHm(turn.createdAt);

  return (
    <article
      aria-label={t("a11y.assistant_at", { time })}
      className="flex w-full justify-start"
    >
      <div className="max-w-[88%] md:max-w-[75%] rounded-2xl border border-border/60 bg-card text-card-foreground px-4 py-3 text-sm">
        <div className="flex items-start gap-2">
          <Info aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <div className="space-y-2">
            <p className="text-muted-foreground">{t(refusalCopyKey(refusal.reason))}</p>

            {refusal.reason === "rate_limited" && refusal.retryAfterSeconds != null && (
              <div className="flex items-center gap-2">
                <RateLimitCountdown
                  retryAfterSeconds={refusal.retryAfterSeconds}
                  onElapsed={() => setElapsed(true)}
                />
                {elapsed && onRetry && (
                  <Button size="sm" variant="outline" onClick={onRetry}>
                    {t("refusal.try_again")}
                  </Button>
                )}
              </div>
            )}

            {refusal.reason === "rate_limited" && refusal.retryAfterSeconds == null && (
              <p className="text-muted-foreground">
                {t("ratelimit.daily_cap", { time: nowLocalHm() })}
              </p>
            )}

            <div className="flex items-center gap-2 pt-1 text-xs text-muted-foreground">
              <span>{t("refusal.copy_reference.label", { id: correlationShort })}</span>
              <span id={`chat-corr-${turn.id}`} className="sr-only">
                {refusal.correlationId}
              </span>
              <button
                type="button"
                onClick={onCopy}
                className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
              >
                <CopyIcon aria-hidden="true" className="h-3 w-3" />
                <span>
                  {copied
                    ? t("refusal.copy_reference.copied_label")
                    : t("refusal.copy_reference.copy_label")}
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}
