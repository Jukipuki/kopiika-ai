import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import React from "react";
import { ProgressiveLoadingState } from "../components/ProgressiveLoadingState";

vi.mock("../components/SkeletonCard", () => ({
  SkeletonCard: () => React.createElement("div", { "data-testid": "skeleton-card" }),
}));

describe("ProgressiveLoadingState", () => {
  it("renders two skeleton cards", () => {
    render(<ProgressiveLoadingState phase={null} />);
    expect(screen.getAllByTestId("skeleton-card")).toHaveLength(2);
  });

  it("shows 'AI is still thinking...' when phase is null", () => {
    render(<ProgressiveLoadingState phase={null} />);
    expect(screen.getByText("AI is still thinking...")).toBeInTheDocument();
  });

  it("shows 'Crunching your numbers...' when phase is 'parsing'", () => {
    render(<ProgressiveLoadingState phase="parsing" />);
    expect(screen.getByText("Crunching your numbers...")).toBeInTheDocument();
  });

  it("shows 'Finding patterns in your spending...' when phase is 'categorization'", () => {
    render(<ProgressiveLoadingState phase="categorization" />);
    expect(screen.getByText("Finding patterns in your spending...")).toBeInTheDocument();
  });

  it("shows 'Almost there... crafting your insights' when phase is 'education'", () => {
    render(<ProgressiveLoadingState phase="education" />);
    expect(screen.getByText("Almost there... crafting your insights")).toBeInTheDocument();
  });

  it("shows default copy for unknown phase", () => {
    render(<ProgressiveLoadingState phase="unknown-phase" />);
    expect(screen.getByText("AI is still thinking...")).toBeInTheDocument();
  });
});
