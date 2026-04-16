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

  // Story 2.9: currency_unknown
  it("maps currency_unknown reason to localized label", () => {
    const txn: FlaggedTransaction = {
      id: "txn-4",
      uploadId: "upload-1",
      date: "2026-03-01",
      description: "Exotic Exchange",
      amount: -10000,
      uncategorizedReason: "currency_unknown",
      currencyUnknownRaw: "XYZ",
    };

    vi.mocked(useFlaggedTransactions).mockReturnValue({
      flaggedTransactions: [txn],
      isLoading: false,
      isError: false,
    });

    render(<UncategorizedTransactions />);

    expect(screen.getByText("Unrecognized currency")).toBeTruthy();
  });

  it("renders raw currency badge when currencyUnknownRaw is present", () => {
    const txn: FlaggedTransaction = {
      id: "txn-5",
      uploadId: "upload-1",
      date: "2026-02-28",
      description: "Mystery Transaction",
      amount: -5000,
      uncategorizedReason: "currency_unknown",
      currencyUnknownRaw: "XYZ",
    };

    vi.mocked(useFlaggedTransactions).mockReturnValue({
      flaggedTransactions: [txn],
      isLoading: false,
      isError: false,
    });

    render(<UncategorizedTransactions />);

    expect(screen.getByText("XYZ")).toBeTruthy();
  });

  it("does not render raw currency badge when currencyUnknownRaw is absent", () => {
    const txn: FlaggedTransaction = {
      id: "txn-6",
      uploadId: "upload-1",
      date: "2026-02-27",
      description: "Low Confidence Item",
      amount: -3000,
      uncategorizedReason: "low_confidence",
    };

    vi.mocked(useFlaggedTransactions).mockReturnValue({
      flaggedTransactions: [txn],
      isLoading: false,
      isError: false,
    });

    render(<UncategorizedTransactions />);

    expect(screen.queryByText(/^[A-Z]{3}$/)).toBeNull();
  });

  it("suppresses currency glyph/code on the amount when currencyUnknownRaw is set", () => {
    // Would be actively misleading to render "−100,00 ₴" (or "UAH 100.00") next to an "XYZ" badge.
    const txn: FlaggedTransaction = {
      id: "txn-7",
      uploadId: "upload-1",
      date: "2026-02-20",
      description: "Exotic Exchange",
      amount: -10000,
      uncategorizedReason: "currency_unknown",
      currencyUnknownRaw: "XYZ",
    };

    vi.mocked(useFlaggedTransactions).mockReturnValue({
      flaggedTransactions: [txn],
      isLoading: false,
      isError: false,
    });

    const { container } = render(<UncategorizedTransactions />);
    const text = container.textContent ?? "";

    // No UAH glyph or alpha code in the rendered amount.
    expect(text).not.toContain("₴");
    // The only "UAH" substring should come from the raw-code badge (which is XYZ),
    // not from formatCurrency's en-US output ("UAH 100.00").
    expect(text).not.toContain("UAH");
    // The raw-code badge is still rendered.
    expect(screen.getByText("XYZ")).toBeTruthy();
  });

  it("still renders currency glyph/code when the reason is not currency_unknown", () => {
    const txn: FlaggedTransaction = {
      id: "txn-8",
      uploadId: "upload-1",
      date: "2026-02-15",
      description: "Low Conf",
      amount: -5000,
      uncategorizedReason: "low_confidence",
    };

    vi.mocked(useFlaggedTransactions).mockReturnValue({
      flaggedTransactions: [txn],
      isLoading: false,
      isError: false,
    });

    const { container } = render(<UncategorizedTransactions />);
    const text = container.textContent ?? "";

    // Intl output varies by locale: "₴50,00" (uk-UA) or "UAH 50.00" (en-US).
    expect(text.includes("₴") || text.includes("UAH")).toBe(true);
  });
});
