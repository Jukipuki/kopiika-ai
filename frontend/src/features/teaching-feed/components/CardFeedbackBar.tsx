"use client";

import { useEffect, useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useCardFeedback } from "../hooks/use-card-feedback";

interface CardFeedbackBarProps {
  cardId: string;
}

export function CardFeedbackBar({ cardId }: CardFeedbackBarProps) {
  const [visible, setVisible] = useState(false);
  const { vote, submitVote, isPending } = useCardFeedback(cardId);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 2000);
    return () => clearTimeout(t);
  }, []);

  if (!visible) return null;

  const handleVote = (value: "up" | "down") => {
    if (vote === value) return;
    if ("vibrate" in navigator) {
      navigator.vibrate(10);
    }
    submitVote(value);
  };

  return (
    <div className="flex gap-2 justify-end">
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        aria-label="Rate this insight helpful"
        aria-pressed={vote === "up"}
        disabled={isPending}
        onClick={() => handleVote("up")}
      >
        <ThumbsUp
          className={cn(
            "h-4 w-4",
            vote === "up"
              ? "fill-primary text-primary"
              : "text-muted-foreground",
          )}
        />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        aria-label="Rate this insight not helpful"
        aria-pressed={vote === "down"}
        disabled={isPending}
        onClick={() => handleVote("down")}
      >
        <ThumbsDown
          className={cn(
            "h-4 w-4",
            vote === "down"
              ? "fill-primary text-primary"
              : "text-muted-foreground",
          )}
        />
      </Button>
    </div>
  );
}
