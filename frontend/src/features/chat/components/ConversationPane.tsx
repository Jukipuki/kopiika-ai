"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { ArrowDown } from "lucide-react";
import { useScrollLock } from "../hooks/useScrollLock";
import { MessageBubble } from "./MessageBubble";
import { RefusalBubble } from "./RefusalBubble";
import { CitationChipRow } from "./CitationChipRow";
import type { ChatTurnState } from "../hooks/useChatStream";

interface Props {
  turns: ChatTurnState[];
  onRetry?: () => void;
}

export function ConversationPane({ turns, onRetry }: Props) {
  const t = useTranslations("chat");
  const { ref, showJumpButton, scrollToBottom, onContentAppended } = useScrollLock<HTMLDivElement>();

  // Append-detect signal — fires on every text/turn change.
  const lastTurn = turns[turns.length - 1];
  const lastTextLen = lastTurn?.text?.length ?? 0;
  useEffect(() => {
    onContentAppended();
  }, [turns.length, lastTextLen, onContentAppended]);

  return (
    <div className="relative flex-1 overflow-hidden">
      <div
        ref={ref}
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label={t("a11y.conversation_label")}
        tabIndex={0}
        className="h-full space-y-4 overflow-y-auto px-4 py-4 focus:outline-none"
      >
        {turns.length === 0 && (
          <p className="text-center text-sm text-muted-foreground">{t("empty.first_message_hint")}</p>
        )}
        {turns.map((turn) => {
          if (turn.refusal) return <RefusalBubble key={turn.id} turn={turn} onRetry={onRetry} />;
          return (
            <div key={turn.id} className="space-y-1">
              <MessageBubble turn={turn} />
              {turn.role === "assistant" && !turn.streaming && turn.citations && (
                <div className="pl-1">
                  <CitationChipRow citations={turn.citations} />
                </div>
              )}
              {turn.disconnected && (
                <div className="pl-1 text-xs text-muted-foreground">
                  <span>{t("streaming.connection_lost")} </span>
                  {onRetry && (
                    <button
                      type="button"
                      onClick={onRetry}
                      className="underline hover:text-foreground"
                    >
                      {t("streaming.retry")}
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {showJumpButton && (
        <button
          type="button"
          onClick={() => scrollToBottom(true)}
          aria-label={t("streaming.scroll_to_bottom")}
          className="absolute bottom-4 right-4 inline-flex items-center gap-1 rounded-full bg-primary px-3 py-1.5 text-xs text-primary-foreground shadow-lg motion-reduce:transition-none"
        >
          <ArrowDown aria-hidden="true" className="h-3 w-3" />
          {t("streaming.scroll_to_bottom")}
        </button>
      )}
    </div>
  );
}
