export type SeverityLevel = "high" | "medium" | "low";

export interface SubscriptionInfo {
  merchantName: string;
  monthlyCostUah: number;
  billingFrequency: "monthly" | "annual";
  isActive: boolean;
  monthsWithNoActivity: number | null;
}

export interface InsightCard {
  id: string;
  uploadId: string | null;
  headline: string;
  keyMetric: string;
  whyItMatters: string;
  deepDive: string;
  severity: SeverityLevel;
  category: string;
  cardType: string; // "insight" | "subscriptionAlert" | "milestoneFeedback"
  subscription: SubscriptionInfo | null;
  createdAt: string;
}

export interface InsightListResponse {
  items: InsightCard[];
  total: number;
  nextCursor: string | null;
  hasMore: boolean;
}
