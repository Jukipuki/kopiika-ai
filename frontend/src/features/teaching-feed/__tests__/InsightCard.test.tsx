import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { InsightCard } from "../components/InsightCard";
import type { InsightCard as InsightCardType } from "../types";

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: null, status: "unauthenticated" }),
}));

const mockInsight: InsightCardType = {
  id: "uuid-1",
  uploadId: null,
  headline: "You spent 30% more on food this month",
  keyMetric: "₴3,200",
  whyItMatters: "Food is your biggest variable expense.",
  deepDive: "Breaking down by category: restaurants 60%, groceries 40%.",
  severity: "high",
  category: "food",
  createdAt: "2026-04-04T12:00:00.000000Z",
};

describe("InsightCard", () => {
  it("renders headline and keyMetric", () => {
    render(<InsightCard insight={mockInsight} />);
    expect(screen.getByText("You spent 30% more on food this month")).toBeInTheDocument();
    expect(screen.getByText("₴3,200")).toBeInTheDocument();
  });

  // Regression guards for Story 4.2 visual hierarchy fix:
  // headline must be visually dominant, key metric must be supporting.
  it("headline renders with text-lg font-bold classes", () => {
    render(<InsightCard insight={mockInsight} />);
    const headline = screen.getByText("You spent 30% more on food this month");
    expect(headline).toHaveClass("text-lg", "font-bold");
  });

  it("key metric renders with supporting style classes", () => {
    render(<InsightCard insight={mockInsight} />);
    const metric = screen.getByText("₴3,200");
    expect(metric).toHaveClass("text-base", "font-medium", "text-muted-foreground", "truncate");
  });

  it("renders TriageBadge with correct severity", () => {
    render(<InsightCard insight={mockInsight} />);
    expect(screen.getByLabelText("High priority insight")).toBeInTheDocument();
  });

  it("shows 'Learn why →' button initially (level 0)", () => {
    render(<InsightCard insight={mockInsight} />);
    expect(screen.getByRole("button", { name: /learn why/i })).toBeInTheDocument();
  });

  it("expands to whyItMatters on first click", () => {
    render(<InsightCard insight={mockInsight} />);
    fireEvent.click(screen.getByRole("button", { name: /learn why/i }));
    expect(screen.getByText(/food is your biggest variable expense/i)).toBeInTheDocument();
  });

  it("shows 'Go deeper →' button after first expansion", () => {
    render(<InsightCard insight={mockInsight} />);
    fireEvent.click(screen.getByRole("button", { name: /learn why/i }));
    expect(screen.getByRole("button", { name: /go deeper/i })).toBeInTheDocument();
  });

  it("expands to deepDive on second click", () => {
    render(<InsightCard insight={mockInsight} />);
    fireEvent.click(screen.getByRole("button", { name: /learn why/i }));
    fireEvent.click(screen.getByRole("button", { name: /go deeper/i }));
    expect(
      screen.getByText(/breaking down by category: restaurants 60%/i),
    ).toBeInTheDocument();
  });

  it("collapses back to level 0 on third click", () => {
    render(<InsightCard insight={mockInsight} />);
    fireEvent.click(screen.getByRole("button", { name: /learn why/i }));
    fireEvent.click(screen.getByRole("button", { name: /go deeper/i }));
    fireEvent.click(screen.getByRole("button", { name: /collapse/i }));
    expect(screen.getByRole("button", { name: /learn why/i })).toBeInTheDocument();
  });

  it("button has aria-expanded false initially", () => {
    render(<InsightCard insight={mockInsight} />);
    const btn = screen.getByRole("button", { name: /learn why/i });
    expect(btn).toHaveAttribute("aria-expanded", "false");
  });

  it("button has aria-expanded true after first expansion", () => {
    render(<InsightCard insight={mockInsight} />);
    fireEvent.click(screen.getByRole("button", { name: /learn why/i }));
    const btn = screen.getByRole("button", { name: /go deeper/i });
    expect(btn).toHaveAttribute("aria-expanded", "true");
  });
});
