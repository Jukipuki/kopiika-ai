export type SeverityLevel = "high" | "medium" | "low";

export interface InsightCard {
  id: string;
  uploadId: string | null;
  headline: string;
  keyMetric: string;
  whyItMatters: string;
  deepDive: string;
  severity: SeverityLevel;
  category: string;
  createdAt: string;
}

export interface InsightListResponse {
  items: InsightCard[];
  total: number;
  nextCursor: string | null;
  hasMore: boolean;
}
