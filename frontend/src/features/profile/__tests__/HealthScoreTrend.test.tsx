import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { HealthScoreTrend } from "../components/HealthScoreTrend";
import type { HealthScoreHistoryItem } from "../types";

// Mock next-intl
vi.mock("next-intl", async () => {
  const { mockNextIntl } = await import("@/test-utils/intl-mock");
  return mockNextIntl;
});

const BREAKDOWN = {
  savings_ratio: 50,
  category_diversity: 50,
  expense_regularity: 50,
  income_coverage: 50,
};

function makeItem(score: number, date: string): HealthScoreHistoryItem {
  return { score, breakdown: BREAKDOWN, calculatedAt: date };
}

describe("HealthScoreTrend", () => {
  beforeEach(() => {
    // Mock matchMedia for prefers-reduced-motion
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query === "(prefers-reduced-motion: reduce)",
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  it("renders nothing when data is empty", () => {
    const { container } = render(<HealthScoreTrend data={[]} locale="en" />);
    expect(container.innerHTML).toBe("");
  });

  it("shows encouraging message for single data point", () => {
    render(
      <HealthScoreTrend
        data={[makeItem(60, "2026-03-01T00:00:00Z")]}
        locale="en"
      />
    );
    expect(
      screen.getByText("Upload more months to track your progress")
    ).toBeTruthy();
    // No SVG chart should be rendered
    expect(document.querySelector("svg")).toBeNull();
  });

  it("renders SVG chart with correct number of data points", () => {
    const data = [
      makeItem(40, "2026-01-01T00:00:00Z"),
      makeItem(60, "2026-02-01T00:00:00Z"),
      makeItem(75, "2026-03-01T00:00:00Z"),
    ];
    render(<HealthScoreTrend data={data} locale="en" />);

    const svg = document.querySelector('svg[role="img"]');
    expect(svg).toBeTruthy();

    // 3 data point circles
    const circles = svg!.querySelectorAll("circle");
    expect(circles.length).toBe(3);
  });

  it("renders polyline connecting all points", () => {
    const data = [
      makeItem(40, "2026-01-01T00:00:00Z"),
      makeItem(75, "2026-03-01T00:00:00Z"),
    ];
    render(<HealthScoreTrend data={data} locale="en" />);

    const polyline = document.querySelector("polyline");
    expect(polyline).toBeTruthy();
    expect(polyline!.getAttribute("points")).toBeTruthy();
  });

  it("has accessible role and aria-label", () => {
    const data = [
      makeItem(40, "2026-01-01T00:00:00Z"),
      makeItem(75, "2026-03-01T00:00:00Z"),
    ];
    render(<HealthScoreTrend data={data} locale="en" />);

    const svg = document.querySelector('svg[role="img"]');
    expect(svg).toBeTruthy();
    const ariaLabel = svg!.getAttribute("aria-label");
    expect(ariaLabel).toContain("Health score trend");
  });

  it("does not apply animation when prefers-reduced-motion", () => {
    const data = [
      makeItem(40, "2026-01-01T00:00:00Z"),
      makeItem(75, "2026-03-01T00:00:00Z"),
    ];
    render(<HealthScoreTrend data={data} locale="en" />);

    const polyline = document.querySelector("polyline");
    expect(polyline).toBeTruthy();
    // No stroke-dasharray animation attributes when reduced motion preferred
    expect(polyline!.getAttribute("stroke-dasharray")).toBeNull();
    expect(polyline!.style.animation).toBe("");
    // No injected keyframe style element
    expect(document.querySelector("style")).toBeNull();
  });

  it("applies line-draw animation when reduced motion is not preferred", () => {
    // Override matchMedia to NOT prefer reduced motion
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    const data = [
      makeItem(40, "2026-01-01T00:00:00Z"),
      makeItem(75, "2026-03-01T00:00:00Z"),
    ];
    render(<HealthScoreTrend data={data} locale="en" />);

    const polyline = document.querySelector("polyline");
    expect(polyline).toBeTruthy();
    // Should have stroke-dasharray set for animation
    expect(polyline!.getAttribute("stroke-dasharray")).toBeTruthy();
    expect(polyline!.style.animation).toContain("draw-line");
    // Keyframe style element should be injected
    const styleEl = document.querySelector("style");
    expect(styleEl).toBeTruthy();
    expect(styleEl!.textContent).toContain("@keyframes draw-line");
  });
});
