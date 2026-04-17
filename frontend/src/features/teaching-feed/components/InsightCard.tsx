"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { TriageBadge } from "./TriageBadge";
import { EducationLayer } from "./EducationLayer";
import { CardFeedbackBar } from "./CardFeedbackBar";
import { useCardInteractions } from "../hooks/use-card-interactions";
import type { InsightCard as InsightCardType } from "../types";

interface InsightCardProps {
  insight: InsightCardType;
  cardPositionInFeed?: number;
}

const BUTTON_LABELS: Record<0 | 1 | 2, string> = {
  0: "Learn why →",
  1: "Go deeper →",
  2: "← Collapse",
};

export function InsightCard({ insight, cardPositionInFeed = 0 }: InsightCardProps) {
  const [expandLevel, setExpandLevel] = useState<0 | 1 | 2>(0);
  const { onEducationExpanded } = useCardInteractions(insight.id, cardPositionInFeed);

  function handleExpandToggle() {
    if (expandLevel === 0) {
      setExpandLevel(1);
      onEducationExpanded(1);
    } else if (expandLevel === 1) {
      setExpandLevel(2);
      onEducationExpanded(2);
    } else {
      setExpandLevel(0);
    }
  }

  const isExpanded = expandLevel > 0;
  const layerId = `education-${insight.id}`;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <TriageBadge severity={insight.severity} />
        </div>
        <h3 className="mt-2 text-lg font-bold leading-snug">{insight.headline}</h3>
        <p className="truncate text-base font-medium text-muted-foreground">{insight.keyMetric}</p>
      </CardHeader>
      <CardContent>
        <EducationLayer
          whyItMatters={insight.whyItMatters}
          deepDive={insight.deepDive}
          isExpanded={isExpanded}
          expandLevel={expandLevel}
          id={layerId}
        />
        <div className="mt-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleExpandToggle}
            aria-expanded={isExpanded}
            aria-controls={`${layerId}-why ${layerId}-deep`}
          >
            {BUTTON_LABELS[expandLevel]}
          </Button>
        </div>
        <CardFeedbackBar cardId={insight.id} />
      </CardContent>
    </Card>
  );
}
