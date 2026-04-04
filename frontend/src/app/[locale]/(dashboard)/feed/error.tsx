"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function FeedError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold">Teaching Feed</h1>
      <Card>
        <CardContent className="p-6 text-center">
          <p className="mb-4 text-sm text-muted-foreground">
            Something went wrong loading the feed.
          </p>
          <Button variant="ghost" size="sm" onClick={reset}>
            Try again
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
