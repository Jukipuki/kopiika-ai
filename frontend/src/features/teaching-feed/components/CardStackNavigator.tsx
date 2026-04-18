"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { InsightCard } from "./InsightCard";
import { SubscriptionAlertCard } from "./SubscriptionAlertCard";
import { SkeletonCard } from "./SkeletonCard";
import { setPendingSwipeDirection } from "../hooks/use-card-interactions";
import type { InsightCard as InsightCardType } from "../types";

function renderCard(card: InsightCardType, index: number) {
  if (card.cardType === "subscriptionAlert" && card.subscription) {
    return <SubscriptionAlertCard insight={card} cardPositionInFeed={index} />;
  }
  return <InsightCard insight={card} cardPositionInFeed={index} />;
}

interface CardStackNavigatorProps {
  cards: InsightCardType[];
  hasNextPage?: boolean;
  isFetchingNextPage?: boolean;
  onLoadMore?: () => void;
}

export function CardStackNavigator({
  cards,
  hasNextPage,
  isFetchingNextPage,
  onLoadMore,
}: CardStackNavigatorProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [direction, setDirection] = useState<1 | -1>(1);
  const containerRef = useRef<HTMLDivElement>(null);
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    containerRef.current?.focus({ preventScroll: true });
  }, []);

  useEffect(() => {
    if (currentIndex >= cards.length && cards.length > 0) {
      setCurrentIndex(cards.length - 1);
    }
  }, [cards.length, currentIndex]);

  if (cards.length === 0) {
    return null;
  }

  function goNext() {
    if (currentIndex < cards.length - 1) {
      setPendingSwipeDirection(cards[currentIndex].id, "right");
      setDirection(1);
      setCurrentIndex((i) => i + 1);
    }
    // Prefetch trigger: within 3 of end
    if (currentIndex >= cards.length - 3 && hasNextPage && !isFetchingNextPage) {
      onLoadMore?.();
    }
  }

  function goPrev() {
    if (currentIndex > 0) {
      setPendingSwipeDirection(cards[currentIndex].id, "left");
      setDirection(-1);
      setCurrentIndex((i) => i - 1);
    }
  }

  const variants = prefersReducedMotion
    ? {
        enter: { opacity: 0 },
        center: { opacity: 1 },
        exit: { opacity: 0 },
      }
    : {
        enter: (dir: number) => ({
          x: dir > 0 ? 300 : -300,
          opacity: 0,
        }),
        center: { x: 0, opacity: 1 },
        exit: (dir: number) => ({
          x: dir > 0 ? -300 : 300,
          opacity: 0,
        }),
      };

  const counterLabel = hasNextPage
    ? `${currentIndex + 1} of ${cards.length}+`
    : `${currentIndex + 1} of ${cards.length}`;

  const isAtLastLoaded = currentIndex === cards.length - 1;
  const isNextDisabled = isAtLastLoaded && !hasNextPage;

  return (
    <div
      ref={containerRef}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight") {
          e.preventDefault();
          goNext();
        }
        if (e.key === "ArrowLeft") {
          e.preventDefault();
          goPrev();
        }
      }}
      className="relative w-full touch-pan-y outline-none"
      aria-label="Insight card stack"
      role="region"
    >
      <span className="sr-only" aria-live="polite">
        Card {counterLabel}
      </span>

      <AnimatePresence mode="wait" custom={direction}>
        <motion.div
          key={currentIndex}
          custom={direction}
          variants={variants}
          initial="enter"
          animate="center"
          exit="exit"
          transition={
            prefersReducedMotion
              ? { duration: 0 }
              : { type: "spring", stiffness: 300, damping: 30 }
          }
          drag={prefersReducedMotion ? false : "x"}
          dragConstraints={{ left: 0, right: 0 }}
          dragElastic={0.7}
          onDragEnd={(_, info) => {
            if (info.offset.x < -80) goNext();
            if (info.offset.x > 80) goPrev();
          }}
        >
          {renderCard(cards[currentIndex], currentIndex)}
        </motion.div>
      </AnimatePresence>

      {isFetchingNextPage && isAtLastLoaded && (
        <div className="mt-2" data-testid="loading-more-skeleton">
          <SkeletonCard />
        </div>
      )}

      <div className="mt-4 flex items-center justify-between">
        <Button
          variant="outline"
          size="icon"
          onClick={goPrev}
          disabled={currentIndex === 0}
          aria-label="Previous insight"
          className="h-11 w-11"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>

        <span className="text-sm text-muted-foreground">
          {counterLabel}
        </span>

        <Button
          variant="outline"
          size="icon"
          onClick={goNext}
          disabled={isNextDisabled}
          aria-label="Next insight"
          className="h-11 w-11"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
