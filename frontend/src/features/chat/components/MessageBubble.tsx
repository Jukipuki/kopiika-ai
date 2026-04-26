"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { ChatTurnState } from "../hooks/useChatStream";

interface Props {
  turn: ChatTurnState;
  children?: React.ReactNode;
}

function formatHm(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function MessageBubble({ turn, children }: Props) {
  const t = useTranslations("chat");
  const isUser = turn.role === "user";
  const time = formatHm(turn.createdAt);
  const ariaLabel = isUser
    ? t("a11y.user_at", { time })
    : t("a11y.assistant_at", { time });

  return (
    <article
      aria-label={ariaLabel}
      aria-busy={!isUser && turn.streaming ? "true" : "false"}
      className={cn(
        "flex w-full",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      <div
        className={cn(
          "rounded-2xl px-4 py-2 text-sm leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere]",
          isUser
            ? "max-w-[88%] md:max-w-[75%] bg-primary text-primary-foreground"
            : "max-w-[88%] md:max-w-[75%] bg-muted text-foreground",
        )}
      >
        {!isUser && turn.thinkingTool && !turn.text && (
          <ThinkingRow toolName={turn.thinkingTool} />
        )}
        {turn.text}
        {!isUser && turn.streaming && turn.text && (
          <span
            aria-hidden="true"
            className="ml-0.5 inline-block h-3 w-[2px] bg-current align-middle motion-safe:animate-pulse motion-reduce:opacity-60"
          />
        )}
        {children}
      </div>
    </article>
  );
}

function ThinkingRow({ toolName }: { toolName: string }) {
  const t = useTranslations("chat");
  const knownKeys = new Set([
    "get_transactions",
    "get_profile",
    "get_teaching_feed",
    "search_financial_corpus",
  ]);
  const key = knownKeys.has(toolName) ? `streaming.thinking_${toolName}` : "streaming.thinking_default";
  return (
    <span className="inline-flex items-center gap-2 italic text-muted-foreground">
      <span aria-hidden="true" className="inline-flex gap-0.5">
        <span className="h-1.5 w-1.5 rounded-full bg-current motion-safe:animate-bounce" />
        <span className="h-1.5 w-1.5 rounded-full bg-current motion-safe:animate-bounce [animation-delay:120ms]" />
        <span className="h-1.5 w-1.5 rounded-full bg-current motion-safe:animate-bounce [animation-delay:240ms]" />
      </span>
      <span>{t(key)}</span>
    </span>
  );
}
