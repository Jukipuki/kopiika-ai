"use client";

import { useEffect, useState } from "react";
import { Flag, MoreHorizontal, ThumbsDown, ThumbsUp } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { useCardFeedback } from "../hooks/use-card-feedback";
import { ReportIssueForm } from "./ReportIssueForm";

interface CardFeedbackBarProps {
  cardId: string;
}

export function CardFeedbackBar({ cardId }: CardFeedbackBarProps) {
  const t = useTranslations("feed.reportIssue");
  const [visible, setVisible] = useState(false);
  const [isReportOpen, setIsReportOpen] = useState(false);
  const { vote, submitVote, isPending } = useCardFeedback(cardId);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), 2000);
    return () => clearTimeout(timer);
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
    <div>
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
        <DropdownMenu>
          <DropdownMenuTrigger
            aria-label={t("openMenu")}
            render={<Button variant="ghost" size="icon" className="h-8 w-8" />}
          >
            <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setIsReportOpen(true)}>
              <Flag className="h-4 w-4 mr-2" />
              {t("trigger")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {isReportOpen && (
        <ReportIssueForm
          cardId={cardId}
          onClose={() => setIsReportOpen(false)}
        />
      )}
    </div>
  );
}
