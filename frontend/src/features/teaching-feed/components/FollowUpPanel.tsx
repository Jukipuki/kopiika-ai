"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import type { ReasonChip } from "../hooks/use-card-feedback";
/* eslint-disable jsx-a11y/no-autofocus */

const CHIPS: ReadonlyArray<{ value: ReasonChip; key: string }> = [
  { value: "not_relevant", key: "chip.notRelevant" },
  { value: "already_knew", key: "chip.alreadyKnew" },
  { value: "seems_incorrect", key: "chip.seemsIncorrect" },
  { value: "hard_to_understand", key: "chip.hardToUnderstand" },
];

interface FollowUpPanelProps {
  onDismiss: () => void;
  onChipSelect?: (chip: ReasonChip) => void;
}

export function FollowUpPanel({ onDismiss, onChipSelect }: FollowUpPanelProps) {
  const t = useTranslations("feed.followUpPanel");
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [selected, setSelected] = useState<ReasonChip | null>(null);
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (dismissTimerRef.current !== null) {
        clearTimeout(dismissTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      const panel = panelRef.current;
      if (panel && !panel.contains(event.target as Node)) {
        onDismiss();
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onDismiss();
      }
    };
    document.addEventListener("pointerdown", handlePointerDown, true);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown, true);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [onDismiss]);

  const handleChipClick = (chip: ReasonChip) => {
    if (selected) return;
    setSelected(chip);
    onChipSelect?.(chip);
    dismissTimerRef.current = setTimeout(onDismiss, 1000);
  };

  return (
    <div
      ref={panelRef}
      role="group"
      aria-labelledby={titleId}
      className="mt-2 rounded-lg border bg-background p-3 shadow-sm animate-in slide-in-from-bottom duration-200"
    >
      <p id={titleId} className="mb-2 text-sm font-medium">
        {t("title")}
      </p>
      <div className="flex flex-wrap gap-2">
        {CHIPS.map(({ value, key }, index) => (
          <Button
            key={value}
            variant="outline"
            size="sm"
            autoFocus={index === 0}
            aria-pressed={selected === value}
            disabled={selected !== null && selected !== value}
            onClick={() => handleChipClick(value)}
          >
            {t(key)}
          </Button>
        ))}
      </div>
    </div>
  );
}
