import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { UncategorizedTransactions } from "../components/UncategorizedTransactions";
import type { FlaggedTransaction } from "../hooks/use-flagged-transactions";

// Mock next-intl
vi.mock("next-intl", async () => {
  const { mockNextIntl } = await import("@/test-utils/intl-mock");
  return mockNextIntl;
});

// Mock the hook
vi.mock("../hooks/use-flagged-transactions", () => ({
  useFlaggedTransactions: vi.fn(),
}));

import { useFlaggedTransactions } from "../hooks/use-flagged-transactions";

const mockFlaggedTransactions: FlaggedTransaction[] = [
  {
    id: "txn-1",
    uploadId: "upload-1",
    date: "2026-03-15",
    description: "Mystery Shop",
    amount: -25000,
    uncategorizedReason: "low_confidence",
  },
  {
    id: "txn-2",
    uploadId: "upload-1",
    date: "2026-03-10",
    description: "Unknown Merchant",
    amount: -10000,
    uncategorizedReason: "parse_failure",
  },
];

describe("UncategorizedTransactions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders null when flaggedTransactions is empty and not loading", () => {
    vi.mocked(useFlaggedTransactions).mockReturnValue({
      flaggedTransactions: [],
      isLoading: false,
      isError: false,
    });

    const { container } = render(<UncategorizedTransactions />);
    expect(container.firstChild).toBeNull();
  });

  it("renders skeleton while loading with no data", () => {
    vi.mocked(useFlaggedTransactions).mockReturnValue({
      flaggedTransactions: [],
      isLoading: true,
      isError: false,
    });

    const { container } = render(<UncategorizedTransactions />);

    // Component should render something (not null) while loading
    expect(container.firstChild).not.toBeNull();
    // Skeleton elements should be present inside the rendered card
    const skeletons = container.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders section title when flagged transactions exist", () => {
    vi.mocked(useFlaggedTransactions).mockReturnValue({
      flaggedTransactions: mockFlaggedTransactions,
      isLoading: false,
      isError: false,
    });

    render(<UncategorizedTransactions />);

    expect(screen.getByText("Transactions we couldn't categorize")).toBeTruthy();
  });

  it("renders explanation text when flagged transactions exist", () => {
    vi.mocked(useFlaggedTransactions).mockReturnValue({
      flaggedTransactions: mockFlaggedTransactions,
      isLoading: false,
      isError: false,
    });

    render(<UncategorizedTransactions />);

    expect(
      screen.getByText("We couldn't figure out a few of these — they won't affect your overall insights")
    ).toBeTruthy();
  });

  it("renders transaction descriptions", () => {
    vi.mocked(useFlaggedTransactions).mockReturnValue({
      flaggedTransactions: mockFlaggedTransactions,
      isLoading: false,
      isError: false,
    });

    render(<UncategorizedTransactions />);

    expect(screen.getByText("Mystery Shop")).toBeTruthy();
    expect(screen.getByText("Unknown Merchant")).toBeTruthy();
  });

  it("maps low_confidence reason to correct i18n key", () => {
    vi.mocked(useFlaggedTransactions).mockReturnValue({
      flaggedTransactions: [mockFlaggedTransactions[0]],
      isLoading: false,
      isError: false,
    });

    render(<UncategorizedTransactions />);

    expect(
      screen.getByText("Our AI wasn't confident enough to categorize this one")
    ).toBeTruthy();
  });

  it("maps parse_failure reason to correct i18n key", () => {
    vi.mocked(useFlaggedTransactions).mockReturnValue({
      flaggedTransactions: [mockFlaggedTransactions[1]],
      isLoading: false,
      isError: false,
    });

    render(<UncategorizedTransactions />);

    expect(
      screen.getByText("Our AI gave an unexpected response for this transaction")
    ).toBeTruthy();
  });

  it("maps llm_unavailable reason to correct i18n key", () => {
    const txn: FlaggedTransaction = {
      id: "txn-3",
      uploadId: "upload-1",
      date: "2026-03-05",
      description: "Weekend Market",
      amount: -5000,
      uncategorizedReason: "llm_unavailable",
    };

    vi.mocked(useFlaggedTransactions).mockReturnValue({
      flaggedTransactions: [txn],
      isLoading: false,
      isError: false,
    });

    render(<UncategorizedTransactions />);

    expect(
      screen.getByText("Our AI was temporarily unavailable when processing this")
    ).toBeTruthy();
  });
});
