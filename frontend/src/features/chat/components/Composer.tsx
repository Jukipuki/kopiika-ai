"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Send } from "lucide-react";

const MAX_CHARS = 4096;
const COUNTER_THRESHOLD = Math.floor(MAX_CHARS * 0.7);

interface Props {
  onSend: (message: string) => void;
  disabled: boolean;
  cooldownActive?: boolean;
  autoFocus?: boolean;
  errorBanner?: React.ReactNode;
}

export function Composer({ onSend, disabled, cooldownActive, autoFocus = true, errorBanner }: Props) {
  const t = useTranslations("chat");
  const [value, setValue] = useState("");
  const [hint, setHint] = useState("");
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const labelId = useId();

  useEffect(() => {
    if (autoFocus) taRef.current?.focus();
  }, [autoFocus]);

  // Auto-grow up to ~5 lines.
  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    const max = parseFloat(getComputedStyle(ta).lineHeight) * 5 + 16;
    ta.style.height = `${Math.min(ta.scrollHeight, max)}px`;
  }, [value]);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled || cooldownActive) {
      if (disabled) setHint(t("composer.send_disabled_hint"));
      else if (cooldownActive) setHint(t("composer.cooldown_hint"));
      return;
    }
    if (trimmed.length > MAX_CHARS) {
      setHint(t("composer.error_too_long"));
      return;
    }
    onSend(trimmed);
    setValue("");
    setHint("");
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter") {
      if (e.shiftKey) return;
      e.preventDefault();
      submit();
    }
  };

  const overThreshold = value.length >= COUNTER_THRESHOLD;
  const overMax = value.length > MAX_CHARS;
  const sendDisabled = disabled || cooldownActive || value.trim().length === 0 || overMax;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="border-t border-border/60 bg-background p-3"
    >
      {errorBanner}
      <label id={labelId} htmlFor="chat-composer-textarea" className="sr-only">
        {t("composer.label")}
      </label>
      <div className="flex items-end gap-2">
        <textarea
          id="chat-composer-textarea"
          ref={taRef}
          value={value}
          aria-labelledby={labelId}
          aria-describedby="chat-composer-hint"
          placeholder={t("composer.placeholder")}
          maxLength={MAX_CHARS}
          onKeyDown={onKeyDown}
          onChange={(e) => setValue(e.target.value)}
          rows={1}
          className="flex-1 resize-none rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-2 focus:outline-ring"
        />
        <button
          type="submit"
          disabled={sendDisabled}
          aria-label={t("composer.send_aria")}
          className="inline-flex h-10 items-center gap-1.5 rounded-lg bg-primary px-3 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          <Send aria-hidden="true" className="h-4 w-4" />
          <span className="hidden sm:inline">{t("composer.send")}</span>
        </button>
      </div>
      <div className="mt-1 flex items-center justify-between text-xs text-muted-foreground">
        <span id="chat-composer-hint" aria-live="polite">{hint}</span>
        {overThreshold && (
          <span className={overMax ? "text-destructive" : ""}>
            {t("composer.char_counter", { count: value.length, max: MAX_CHARS })}
          </span>
        )}
      </div>
    </form>
  );
}
