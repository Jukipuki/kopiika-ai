import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import React from "react";
import { ProgressiveLoadingState } from "../components/ProgressiveLoadingState";

vi.mock("next-intl", async () => {
  const { mockNextIntl } = await import("@/test-utils/intl-mock");
  return mockNextIntl;
});

vi.mock("../components/SkeletonCard", () => ({
  SkeletonCard: () => React.createElement("div", { "data-testid": "skeleton-card" }),
}));

describe("ProgressiveLoadingState", () => {
  it("renders two skeleton cards", () => {
    render(<ProgressiveLoadingState message={null} />);
    expect(screen.getAllByTestId("skeleton-card")).toHaveLength(2);
  });

  it("renders the message prop directly", () => {
    render(<ProgressiveLoadingState message="Categorizing your transactions..." />);
    expect(screen.getByText("Categorizing your transactions...")).toBeInTheDocument();
  });

  it("shows 'Processing...' when message is null", () => {
    render(<ProgressiveLoadingState message={null} />);
    expect(screen.getByText("Processing...")).toBeInTheDocument();
  });

  it("renders any arbitrary backend message without code changes", () => {
    render(<ProgressiveLoadingState message="Aggregating your financial profile..." />);
    expect(screen.getByText("Aggregating your financial profile...")).toBeInTheDocument();
  });
});
