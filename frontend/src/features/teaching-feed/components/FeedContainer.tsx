"use client";

import { Link } from "@/i18n/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useTeachingFeed } from "../hooks/use-teaching-feed";
import { InsightCard } from "./InsightCard";
import { SkeletonCard } from "./SkeletonCard";

export function FeedContainer() {
  const { data, isLoading, isError } = useTeachingFeed();
  const queryClient = useQueryClient();

  if (isLoading) {
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

  if (isError) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <p className="mb-4 text-sm text-muted-foreground">
            Failed to load insights. Please try again.
          </p>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => queryClient.invalidateQueries({ queryKey: ["teaching-feed"] })}
          >
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <p className="text-sm text-muted-foreground">
            No insights yet. Upload a bank statement to get started.{" "}
            <Link href="/upload" className="underline">
              Go to Upload
            </Link>
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <ul className="flex flex-col gap-4">
      {data.map((insight) => (
        <li key={insight.id}>
          <InsightCard insight={insight} />
        </li>
      ))}
    </ul>
  );
}
