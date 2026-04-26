"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

interface Props {
  retryAfterSeconds: number;
  onElapsed?: () => void;
}

function fmt(seconds: number): string {
  const m = Math.floor(seconds / 60).toString().padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

export function RateLimitCountdown({ retryAfterSeconds, onElapsed }: Props) {
  const t = useTranslations("chat");
  const [remaining, setRemaining] = useState(Math.max(0, Math.floor(retryAfterSeconds)));
  // Announce only on mount and on reaching 0 — keep `aria-live="off"` after
  // the initial announce per AC #7 / AC #12.
  const [live, setLive] = useState<"polite" | "off">("polite");

  useEffect(() => {
    if (remaining <= 0) return;
    const handle = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) {
          clearInterval(handle);
          // Defer parent callback + live-flip to avoid setState-during-render
          // warnings when the parent renders a button that mounts mid-tick.
          setTimeout(() => {
            setLive("polite");
            onElapsed?.();
          }, 0);
          return 0;
        }
        return r - 1;
      });
    }, 1000);
    const tt = setTimeout(() => setLive("off"), 100);
    return () => {
      clearInterval(handle);
      clearTimeout(tt);
    };
  }, [remaining, onElapsed]);

  return (
    <span aria-live={live} className="font-mono tabular-nums text-sm">
      {remaining > 0 ? t("ratelimit.cooldown", { time: fmt(remaining) }) : t("ratelimit.cooldown_done")}
    </span>
  );
}
