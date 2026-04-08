"use client";

import { useEffect } from "react";
import { Link } from "@/i18n/navigation";
import { useSession } from "next-auth/react";
import { useTranslations } from "next-intl";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useTeachingFeed } from "../hooks/use-teaching-feed";
import { useFeedSSE } from "../hooks/use-feed-sse";
import { CardStackNavigator } from "./CardStackNavigator";
import { SkeletonCard } from "./SkeletonCard";
import { ProgressiveLoadingState } from "./ProgressiveLoadingState";

interface FeedContainerProps {
  jobId?: string;
}

export function FeedContainer({ jobId }: FeedContainerProps) {
  const { data: session } = useSession();
  const t = useTranslations("feed");
  const { cards, fetchNextPage, hasNextPage, isFetchingNextPage, isFetchNextPageError, isLoading, isError } = useTeachingFeed();
  const queryClient = useQueryClient();
  const { pendingInsightIds, isStreaming, message } = useFeedSSE(jobId ?? null, session?.accessToken);

  // Refetch feed data as new insights arrive from SSE
  useEffect(() => {
    if (pendingInsightIds.length > 0) {
      queryClient.invalidateQueries({ queryKey: ["teaching-feed"] });
    }
  }, [pendingInsightIds.length, queryClient]);

  if (isStreaming && (!cards || cards.length === 0)) {
    return <ProgressiveLoadingState message={message} />;
  }

  if (isLoading && !isStreaming) {
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
      {isStreaming && <ProgressiveLoadingState message={message} />}
    </div>
  );
}
