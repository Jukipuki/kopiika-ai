"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { motion, useReducedMotion } from "motion/react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type MilestoneCardType =
  | "milestone_3rd_upload"
  | "health_score_change";

interface MilestoneFeedbackCardProps {
  cardType: MilestoneCardType;
  onRespond: (responseValue: string, freeText?: string) => void;
  onDismiss: () => void;
  isSubmitting?: boolean;
}

// Matches CardStackNavigator's swipe threshold so the two card types feel
// identical under the finger (AC #3: "same swipe gestures as education cards").
const SWIPE_DISMISS_THRESHOLD_PX = 80;

const EMOJI_OPTIONS: ReadonlyArray<{
  value: "happy" | "neutral" | "sad";
  labelKey: "emojiHappy" | "emojiNeutral" | "emojiSad";
  testId: "emoji-happy" | "emoji-neutral" | "emoji-sad";
}> = [
  { value: "happy", labelKey: "emojiHappy", testId: "emoji-happy" },
  { value: "neutral", labelKey: "emojiNeutral", testId: "emoji-neutral" },
  { value: "sad", labelKey: "emojiSad", testId: "emoji-sad" },
];

const YES_NO_OPTIONS: ReadonlyArray<{
  value: "yes" | "no";
  labelKey: "yes" | "no";
  testId: "response-yes" | "response-no";
}> = [
  { value: "yes", labelKey: "yes", testId: "response-yes" },
  { value: "no", labelKey: "no", testId: "response-no" },
];

export function MilestoneFeedbackCard({
  cardType,
  onRespond,
  onDismiss,
  isSubmitting = false,
}: MilestoneFeedbackCardProps) {
  const t = useTranslations("feed.milestoneFeedback");
  const prefersReducedMotion = useReducedMotion();
  const [selected, setSelected] = useState<string | null>(null);
  const [freeText, setFreeText] = useState("");

  const isEmojiVariant = cardType === "milestone_3rd_upload";
  const title = isEmojiVariant
    ? t("thirdUploadTitle")
    : t("healthScoreTitle");

  const handleSubmit = () => {
    if (!selected) return;
    onRespond(selected, freeText || undefined);
  };

  return (
    <motion.div
      data-testid="milestone-feedback-card-drag"
      className="touch-pan-y"
      drag={prefersReducedMotion ? false : "x"}
      dragConstraints={{ left: 0, right: 0 }}
      dragElastic={0.7}
      onDragEnd={(_, info) => {
        if (Math.abs(info.offset.x) > SWIPE_DISMISS_THRESHOLD_PX) {
          onDismiss();
        }
      }}
    >
      <Card data-testid="milestone-feedback-card">
        <CardHeader className="pb-2">
          <h3 className="text-lg font-semibold leading-snug">{title}</h3>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {isEmojiVariant ? (
            <div className="flex gap-2">
              {EMOJI_OPTIONS.map((opt) => (
                <Button
                  key={opt.value}
                  type="button"
                  variant="outline"
                  size="sm"
                  data-testid={opt.testId}
                  aria-pressed={selected === opt.value}
                  className={cn(
                    "flex-1",
                    selected === opt.value && "border-primary bg-primary/10",
                  )}
                  onClick={() => setSelected(opt.value)}
                >
                  {t(opt.labelKey)}
                </Button>
              ))}
            </div>
          ) : (
            <div className="flex gap-2">
              {YES_NO_OPTIONS.map((opt) => (
                <Button
                  key={opt.value}
                  type="button"
                  variant="outline"
                  size="sm"
                  data-testid={opt.testId}
                  aria-pressed={selected === opt.value}
                  className={cn(
                    "flex-1",
                    selected === opt.value && "border-primary bg-primary/10",
                  )}
                  onClick={() => setSelected(opt.value)}
                >
                  {t(opt.labelKey)}
                </Button>
              ))}
            </div>
          )}

          <label htmlFor="milestone-free-text" className="sr-only">
            {t("optionalComment")}
          </label>
          <textarea
            id="milestone-free-text"
            className="w-full resize-none rounded border p-2 text-sm"
            rows={2}
            maxLength={500}
            placeholder={t("optionalComment")}
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
          />

          <div className="flex items-center justify-between">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              data-testid="milestone-skip"
              onClick={onDismiss}
            >
              {t("skip")}
            </Button>
            <Button
              type="button"
              size="sm"
              data-testid="milestone-submit"
              disabled={!selected || isSubmitting}
              onClick={handleSubmit}
            >
              {t("submit")}
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
