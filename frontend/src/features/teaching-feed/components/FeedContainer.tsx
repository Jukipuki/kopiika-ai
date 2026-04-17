"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Link } from "@/i18n/navigation";
import { useSession } from "next-auth/react";
import { useTranslations } from "next-intl";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useTeachingFeed } from "../hooks/use-teaching-feed";
import { useFeedSSE } from "../hooks/use-feed-sse";
import { useMilestoneFeedback } from "../hooks/use-milestone-feedback";
import { CardStackNavigator } from "./CardStackNavigator";
import { MilestoneFeedbackCard } from "./MilestoneFeedbackCard";
import { SkeletonCard } from "./SkeletonCard";
import { ProgressiveLoadingState } from "./ProgressiveLoadingState";
import { FeedDisclaimer } from "./FeedDisclaimer";

function SkeletonList() {
  return (
    <ul className="flex flex-col gap-4" aria-label="Loading insights">
      {[1, 2, 3].map((i) => (
        <li key={i}>
          <SkeletonCard />
        </li>
      ))}
    </ul>
  );
}

interface FeedContainerProps {
  jobId?: string;
}

export function FeedContainer({ jobId }: FeedContainerProps) {
  const { data: session } = useSession();
  const t = useTranslations("feed");
  const { cards, fetchNextPage, hasNextPage, isFetchingNextPage, isFetchNextPageError, isLoading, isError, isFetching } = useTeachingFeed();
  const queryClient = useQueryClient();
  const { pendingInsightIds, isStreaming, message } = useFeedSSE(jobId ?? null, session?.accessToken);
  const { pendingCard, submitResponse, isPending: isSubmittingMilestone } = useMilestoneFeedback();

  // Refetch feed data as new insights arrive from SSE
  useEffect(() => {
    if (pendingInsightIds.length > 0) {
      queryClient.invalidateQueries({ queryKey: ["teaching-feed"] });
    }
  }, [pendingInsightIds.length, queryClient]);

  // Track streaming→idle transition to scope the empty-state race condition guard.
  // Without this, any background refetch on an empty feed would flash skeletons.
  const wasStreamingRef = useRef(false);
  useEffect(() => {
    if (isStreaming) {
      wasStreamingRef.current = true;
    } else if (!isFetching) {
      wasStreamingRef.current = false;
    }
  }, [isStreaming, isFetching]);

  if (isStreaming && (!cards || cards.length === 0)) {
    return <ProgressiveLoadingState message={message} />;
  }

  if (isLoading && !isStreaming) {
    return <SkeletonList />;
  }

  if (isError && (!cards || cards.length === 0)) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <p className="mb-4 text-sm text-muted-foreground">
            {t("loadFailed")}
          </p>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => queryClient.invalidateQueries({ queryKey: ["teaching-feed"] })}
          >
            {t("retry")}
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!cards || cards.length === 0) {
    // Prevent empty-state flash during the brief window after streaming ends
    // while TanStack Query is refetching (race condition: isStreaming=false before refetch completes).
    // Scoped to post-streaming transition only — background refetches on a genuinely empty feed
    // should keep showing the empty state, not flash skeletons.
    if (wasStreamingRef.current && (isFetching || isLoading)) {
      return <SkeletonList />;
    }
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <p className="text-sm text-muted-foreground">
            {t("noInsights")}{" "}
            <Link href="/upload" className="underline">
              {t("goToUpload")}
            </Link>
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <CardStackNavigator
        cards={cards}
        hasNextPage={hasNextPage}
        isFetchingNextPage={isFetchingNextPage}
        onLoadMore={fetchNextPage}
      />
      {pendingCard && !isStreaming && (
        <MilestoneFeedbackCard
          cardType={pendingCard.cardType}
          isSubmitting={isSubmittingMilestone}
          onRespond={(responseValue, freeText) =>
            submitResponse({
              cardType: pendingCard.cardType,
              responseValue,
              freeText,
            })
          }
          onDismiss={() =>
            submitResponse({
              cardType: pendingCard.cardType,
              responseValue: "dismissed",
            })
          }
        />
      )}
      <FeedDisclaimer />
      {isFetchNextPageError && (
        <Card>
          <CardContent className="p-4 text-center">
            <p className="mb-2 text-sm text-muted-foreground">
              {t("loadMoreFailed")}
            </p>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => fetchNextPage()}
            >
              {t("retry")}
            </Button>
          </CardContent>
        </Card>
      )}
      <AnimatePresence>
        {isStreaming && (
          <motion.div
            key="inline-streaming"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <ProgressiveLoadingState message={message} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
