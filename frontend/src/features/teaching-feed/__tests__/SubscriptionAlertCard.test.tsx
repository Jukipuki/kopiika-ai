import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SubscriptionAlertCard } from "../components/SubscriptionAlertCard";
import type { InsightCard as InsightCardType } from "../types";

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: null, status: "unauthenticated" }),
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("../hooks/use-card-feedback", () => ({
  useCardFeedback: () => ({ vote: null, submitVote: vi.fn(), isPending: false }),
}));

vi.mock("../hooks/use-issue-report", () => ({
  useIssueReport: () => ({
    submitReport: vi.fn(),
    isPending: false,
    isAlreadyReported: false,
    confirmationShown: false,
  }),
}));

function buildInsight(overrides: Partial<InsightCardType> = {}): InsightCardType {
  return {
    id: "sub-uuid-1",
    uploadId: null,
    headline: "netflix ua subscription",
    keyMetric: "₴300.00/month",
    whyItMatters: "You have an active monthly subscription to netflix ua.",
    deepDive: "Last charge: 2026-03-16. Currently active.",
    severity: "medium",
    category: "subscriptions",
    cardType: "subscriptionAlert",
    subscription: {
      merchantName: "netflix ua",
      monthlyCostUah: 300,
      billingFrequency: "monthly",
      isActive: true,
      monthsWithNoActivity: null,
    },
    createdAt: "2026-04-04T12:00:00.000000Z",
    ...overrides,
  };
}

describe("SubscriptionAlertCard", () => {
  it("renders merchant name, monthly cost, and monthly billing frequency label", () => {
    render(<SubscriptionAlertCard insight={buildInsight()} />);
    expect(screen.getByText("netflix ua")).toBeInTheDocument();
    expect(screen.getByText("₴300.00/month")).toBeInTheDocument();
    expect(screen.getByText("Monthly subscription")).toBeInTheDocument();
  });

  it("renders annual billing frequency label for annual cadence", () => {
    const insight = buildInsight({
      subscription: {
        merchantName: "adobe creative cloud",
        monthlyCostUah: 500,
        billingFrequency: "annual",
        isActive: true,
        monthsWithNoActivity: null,
      },
    });
    render(<SubscriptionAlertCard insight={insight} />);
    expect(screen.getByText("Annual subscription")).toBeInTheDocument();
  });

  it("renders inactivity badge when isActive is false", () => {
    const insight = buildInsight({
      subscription: {
        merchantName: "netflix ua",
        monthlyCostUah: 300,
        billingFrequency: "monthly",
        isActive: false,
        monthsWithNoActivity: 2,
      },
    });
    render(<SubscriptionAlertCard insight={insight} />);
    expect(screen.getByText("Inactive 2 month(s)")).toBeInTheDocument();
  });

  it("does NOT render inactivity badge when isActive is true", () => {
    render(<SubscriptionAlertCard insight={buildInsight()} />);
    expect(screen.queryByText(/Inactive \d+ month/)).not.toBeInTheDocument();
  });

  it("renders nothing when subscription data is missing", () => {
    const insight = buildInsight();
    insight.subscription = null;
    const { container } = render(<SubscriptionAlertCard insight={insight} />);
    expect(container.firstChild).toBeNull();
  });
});
