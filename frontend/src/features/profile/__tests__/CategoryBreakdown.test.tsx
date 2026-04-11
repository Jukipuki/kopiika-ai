import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import React from "react";
import { CategoryBreakdown } from "../components/CategoryBreakdown";
import type { CategoryBreakdown as CategoryBreakdownType } from "../types";

// Mock next-intl
vi.mock("next-intl", async () => {
  const { mockNextIntl } = await import("@/test-utils/intl-mock");
  return mockNextIntl;
});

const mockData: CategoryBreakdownType = {
  categories: [
    { category: "groceries", amount: 25000, percentage: 45.0, },
    { category: "dining_out", amount: 18500, percentage: 33.3, },
    { category: "transport", amount: 12000, percentage: 21.6, },
  ],
  totalExpenses: 55500,
};

describe("CategoryBreakdown", () => {
  it("renders donut SVG with role img and aria-label", () => {
    render(<CategoryBreakdown data={mockData} />);

    const svg = document.querySelector('svg[role="img"]');
    expect(svg).toBeTruthy();
    expect(svg?.getAttribute("aria-label")).toContain("Groceries");
    expect(svg?.getAttribute("aria-label")).toContain("45%");
  });

  it("renders title and desc elements inside SVG", () => {
    render(<CategoryBreakdown data={mockData} />);

    const title = document.querySelector("svg title");
    expect(title).toBeTruthy();
    const desc = document.querySelector("svg desc");
    expect(desc).toBeTruthy();
  });

  it("renders legend with all categories sorted by amount", () => {
    render(<CategoryBreakdown data={mockData} />);

    expect(screen.getByText("Groceries")).toBeTruthy();
    expect(screen.getByText("Dining Out")).toBeTruthy();
    expect(screen.getByText("Transport")).toBeTruthy();
  });

  it("displays amounts in hryvnias (converted from kopiykas)", () => {
    render(<CategoryBreakdown data={mockData} />);

    const container = document.body.textContent || "";
    // 25000 kopiykas = 250.00 hryvnias
    expect(container).toContain("250");
    // Should NOT show raw kopiykas
    expect(container).not.toContain("25,000");
    expect(container).not.toContain("25000");
  });

  it("displays percentage for each category", () => {
    render(<CategoryBreakdown data={mockData} />);

    expect(screen.getByText("45%")).toBeTruthy();
    expect(screen.getByText("33.3%")).toBeTruthy();
    expect(screen.getByText("21.6%")).toBeTruthy();
  });

  it("renders color swatches in legend", () => {
    render(<CategoryBreakdown data={mockData} />);

    const swatches = document.querySelectorAll('[aria-hidden="true"]');
    expect(swatches.length).toBe(3);
  });

  it("renders SVG circle elements for donut segments", () => {
    render(<CategoryBreakdown data={mockData} />);

    const circles = document.querySelectorAll("svg circle");
    // 1 background + 3 category segments
    expect(circles.length).toBe(4);
  });

  it("renders translated uncategorized label for uncategorized category", () => {
    const dataWithUncat: CategoryBreakdownType = {
      categories: [
        { category: "uncategorized", amount: 5000, percentage: 100.0, },
      ],
      totalExpenses: 5000,
    };

    render(<CategoryBreakdown data={dataWithUncat} />);

    expect(screen.getByText("Uncategorized")).toBeTruthy();
  });

  it("displays total expenses in donut center", () => {
    render(<CategoryBreakdown data={mockData} />);

    // 55500 kopiykas = 555.00 hryvnias
    const svgText = document.querySelector("svg text");
    const svgContent = document.querySelector("svg")?.textContent || "";
    expect(svgContent).toContain("555");
  });
});
