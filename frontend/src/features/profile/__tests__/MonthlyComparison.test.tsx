import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import React from "react";
import { MonthlyComparison } from "../components/MonthlyComparison";
import type { MonthlyComparison as MonthlyComparisonType } from "../types";

// Mock next-intl
vi.mock("next-intl", async () => {
  const { mockNextIntl } = await import("@/test-utils/intl-mock");
  return mockNextIntl;
});

const mockData: MonthlyComparisonType = {
  currentMonth: "2026-03",
  previousMonth: "2026-02",
  categories: [
    { category: "food", currentAmount: 12000, previousAmount: 10000, changePercent: 20.0, changeAmount: 2000 },
    { category: "transport", currentAmount: 3000, previousAmount: 5000, changePercent: -40.0, changeAmount: -2000 },
    { category: "entertainment", currentAmount: 5000, previousAmount: 5000, changePercent: 0.0, changeAmount: 0 },
    { category: "uncategorized", currentAmount: 2000, previousAmount: 0, changePercent: 100.0, changeAmount: 2000 },
  ],
  totalCurrent: 22000,
  totalPrevious: 20000,
  totalChangePercent: 10.0,
};

describe("MonthlyComparison", () => {
  it("renders category rows with correct names", () => {
    render(<MonthlyComparison data={mockData} />);

    expect(screen.getByText("food")).toBeTruthy();
    expect(screen.getByText("transport")).toBeTruthy();
    expect(screen.getByText("entertainment")).toBeTruthy();
    expect(screen.getByText("Uncategorized")).toBeTruthy();
  });

  it("renders title", () => {
    render(<MonthlyComparison data={mockData} />);

    expect(screen.getByText("Month-over-Month Spending")).toBeTruthy();
  });

  it("shows up-arrow for spending increase", () => {
    render(<MonthlyComparison data={mockData} />);

    // Food increased 20% — should have up arrow
    const upArrows = screen.getAllByText("↑");
    expect(upArrows.length).toBeGreaterThan(0);
  });

  it("shows down-arrow for spending decrease", () => {
    render(<MonthlyComparison data={mockData} />);

    // Transport decreased 40% — should have down arrow
    const downArrows = screen.getAllByText("↓");
    expect(downArrows.length).toBeGreaterThan(0);
  });

  it("shows dash for no change", () => {
    render(<MonthlyComparison data={mockData} />);

    // Entertainment unchanged — should have dash
    const dashes = screen.getAllByText("–");
    expect(dashes.length).toBeGreaterThan(0);
  });

  it("renders positive percentage for increase", () => {
    render(<MonthlyComparison data={mockData} />);

    expect(screen.getByText("+20%")).toBeTruthy();
  });

  it("renders negative percentage for decrease", () => {
    render(<MonthlyComparison data={mockData} />);

    expect(screen.getByText("-40%")).toBeTruthy();
  });

  it("renders 0% for no change", () => {
    render(<MonthlyComparison data={mockData} />);

    const zeroPercents = screen.getAllByText("0%");
    expect(zeroPercents.length).toBeGreaterThan(0);
  });

  it("renders total spending row", () => {
    render(<MonthlyComparison data={mockData} />);

    expect(screen.getByText("Total Spending")).toBeTruthy();
  });

  it("has accessible direction indicators with screen reader text", () => {
    render(<MonthlyComparison data={mockData} />);

    // Screen reader text for increase/decrease/no change
    const srTexts = document.querySelectorAll(".sr-only");
    expect(srTexts.length).toBeGreaterThan(0);

    const srTextContents = Array.from(srTexts).map((el) => el.textContent);
    expect(srTextContents).toContain("increase");
    expect(srTextContents).toContain("decrease");
    expect(srTextContents).toContain("no change");
  });

  it("renders uncategorized with i18n label", () => {
    render(<MonthlyComparison data={mockData} />);

    // "uncategorized" category should render as "Uncategorized" (from i18n)
    expect(screen.getByText("Uncategorized")).toBeTruthy();
  });

  it("formats currency amounts from kopiykas to hryvnias", () => {
    render(<MonthlyComparison data={mockData} />);

    // 12000 kopiykas = 120.00 UAH — look for the formatted amount in the document
    // Food category has currentAmount: 12000 (kopiykas) → ₴120.00 or UAH 120.00
    const container = document.body.textContent || "";
    expect(container).toContain("120");
    // 30 kopiykas = 0.30 should NOT appear as "3000" (raw kopiykas)
    expect(container).not.toContain("12,000");
    expect(container).not.toContain("12000");
  });

  it("renders subtitle with formatted month names", () => {
    render(<MonthlyComparison data={mockData} />);

    // The subtitle should contain formatted month names, not raw "2026-03"
    const container = document.body.textContent || "";
    // Should NOT show raw ISO format in the rendered output
    expect(container).not.toContain("2026-03");
    expect(container).not.toContain("2026-02");
    // Should contain the "vs" keyword from subtitle i18n
    expect(container).toContain("vs");
  });
});
