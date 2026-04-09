import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import React from "react";
import { HealthScoreRing } from "../components/HealthScoreRing";

// Mock next-intl
vi.mock("next-intl", async () => {
  const { mockNextIntl } = await import("@/test-utils/intl-mock");
  return mockNextIntl;
});

const baseBreakdown = {
  savings_ratio: 80,
  category_diversity: 65,
  expense_regularity: 70,
  income_coverage: 60,
};

describe("HealthScoreRing", () => {
  it("renders score number centered", () => {
    render(<HealthScoreRing score={72} breakdown={baseBreakdown} />);
    expect(screen.getByText("72")).toBeTruthy();
  });

  it("renders correct zone label for needs attention (0-30)", () => {
    render(<HealthScoreRing score={20} breakdown={baseBreakdown} />);
    expect(screen.getByText("Needs Attention")).toBeTruthy();
  });

  it("renders correct zone label for developing (31-60)", () => {
    render(<HealthScoreRing score={45} breakdown={baseBreakdown} />);
    expect(screen.getByText("Developing")).toBeTruthy();
  });

  it("renders correct zone label for healthy (61-80)", () => {
    render(<HealthScoreRing score={72} breakdown={baseBreakdown} />);
    expect(screen.getByText("Healthy")).toBeTruthy();
  });

  it("renders correct zone label for excellent (81-100)", () => {
    render(<HealthScoreRing score={90} breakdown={baseBreakdown} />);
    expect(screen.getByText("Excellent")).toBeTruthy();
  });

  it("renders SVG with correct aria-label", () => {
    render(<HealthScoreRing score={72} breakdown={baseBreakdown} />);
    const svg = screen.getByRole("img");
    expect(svg.getAttribute("aria-label")).toContain("72");
  });

  it("shows breakdown on button click", async () => {
    const user = userEvent.setup();
    render(<HealthScoreRing score={72} breakdown={baseBreakdown} />);

    // Breakdown not visible initially
    expect(screen.queryByText("80/100")).toBeNull();

    // Click show breakdown
    await user.click(screen.getByText("Show breakdown"));

    // Breakdown values visible
    expect(screen.getByText("80/100")).toBeTruthy();
    expect(screen.getByText("65/100")).toBeTruthy();
    expect(screen.getByText("70/100")).toBeTruthy();
    expect(screen.getByText("60/100")).toBeTruthy();

    // Component labels visible
    expect(screen.getByText("Savings Ratio")).toBeTruthy();
    expect(screen.getByText("Category Diversity")).toBeTruthy();
    expect(screen.getByText("Expense Regularity")).toBeTruthy();
    expect(screen.getByText("Income Coverage")).toBeTruthy();
  });

  it("hides breakdown on second click", async () => {
    const user = userEvent.setup();
    render(<HealthScoreRing score={72} breakdown={baseBreakdown} />);

    await user.click(screen.getByText("Show breakdown"));
    expect(screen.getByText("80/100")).toBeTruthy();

    await user.click(screen.getByText("Hide breakdown"));
    expect(screen.queryByText("80/100")).toBeNull();
  });

  it("disables animation when prefers-reduced-motion is enabled", () => {
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query === "(prefers-reduced-motion: reduce)",
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
    }));

    const { container } = render(
      <HealthScoreRing score={72} breakdown={baseBreakdown} />
    );
    const scoreCircle = container.querySelectorAll("circle")[1];
    expect(scoreCircle?.style.transition).toBe("none");

    window.matchMedia = originalMatchMedia;
  });

  it("enables animation when prefers-reduced-motion is not set", () => {
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
    }));

    const { container } = render(
      <HealthScoreRing score={72} breakdown={baseBreakdown} />
    );
    const scoreCircle = container.querySelectorAll("circle")[1];
    expect(scoreCircle?.style.transition).toContain("stroke-dashoffset");

    window.matchMedia = originalMatchMedia;
  });

  it("applies correct gradient color for each zone", () => {
    const { container: c1 } = render(
      <HealthScoreRing score={20} breakdown={baseBreakdown} />
    );
    const gradient1 = c1.querySelector("linearGradient stop");
    expect(gradient1?.getAttribute("stop-color")).toBe("#F87171");

    const { container: c2 } = render(
      <HealthScoreRing score={45} breakdown={baseBreakdown} />
    );
    const gradient2 = c2.querySelector("linearGradient stop");
    expect(gradient2?.getAttribute("stop-color")).toBe("#FBBF24");

    const { container: c3 } = render(
      <HealthScoreRing score={72} breakdown={baseBreakdown} />
    );
    const gradient3 = c3.querySelector("linearGradient stop");
    expect(gradient3?.getAttribute("stop-color")).toBe("#8B5CF6");

    const { container: c4 } = render(
      <HealthScoreRing score={90} breakdown={baseBreakdown} />
    );
    const gradient4 = c4.querySelector("linearGradient stop");
    expect(gradient4?.getAttribute("stop-color")).toBe("#2DD4BF");
  });
});
