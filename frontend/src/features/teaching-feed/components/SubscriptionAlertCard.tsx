"use client";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { TriageBadge } from "./TriageBadge";
import { CardFeedbackBar } from "./CardFeedbackBar";
import type { InsightCard as InsightCardType } from "../types";

interface SubscriptionAlertCardProps {
  insight: InsightCardType;
  cardPositionInFeed?: number;
}

export function SubscriptionAlertCard({ insight }: SubscriptionAlertCardProps) {
  const subscription = insight.subscription;
  if (!subscription) {
    return null;
  }

  const frequencyLabel =
    subscription.billingFrequency === "monthly"
      ? "Monthly subscription"
      : "Annual subscription";
  const monthlyCostDisplay = `₴${subscription.monthlyCostUah.toFixed(2)}/month`;
  const inactivityBadgeText =
    subscription.isActive === false
      ? `Inactive ${subscription.monthsWithNoActivity ?? 0} month(s)`
      : null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <TriageBadge severity={insight.severity} />
          {inactivityBadgeText && (
            <span
              className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900"
              aria-label="Inactive subscription"
            >
              {inactivityBadgeText}
            </span>
          )}
        </div>
        <h3 className="mt-2 text-lg font-bold leading-snug">
          {subscription.merchantName}
        </h3>
        <p className="truncate text-base font-medium text-muted-foreground">
          {monthlyCostDisplay}
        </p>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">{frequencyLabel}</p>
        <CardFeedbackBar cardId={insight.id} />
      </CardContent>
    </Card>
  );
}
