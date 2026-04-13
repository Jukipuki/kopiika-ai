import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { ProfilePage } from "../components/ProfilePage";

// Mock next-intl
vi.mock("next-intl", async () => {
  const { mockNextIntl } = await import("@/test-utils/intl-mock");
  return mockNextIntl;
});

// Mock next-auth/react
const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

// Mock @/i18n/navigation
vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...props }: { href: string; children: React.ReactNode }) =>
    React.createElement("a", { href, ...props }, children),
}));

// Mock useProfile hook
const mockUseProfile = vi.fn();
vi.mock("../hooks/use-profile", () => ({
  useProfile: () => mockUseProfile(),
}));

// Mock useHealthScore hook
const mockUseHealthScore = vi.fn();
vi.mock("../hooks/use-health-score", () => ({
  useHealthScore: () => mockUseHealthScore(),
}));

// Mock useHealthScoreHistory hook
const mockUseHealthScoreHistory = vi.fn();
vi.mock("../hooks/use-health-score-history", () => ({
  useHealthScoreHistory: () => mockUseHealthScoreHistory(),
}));

// Mock useMonthlyComparison hook
const mockUseMonthlyComparison = vi.fn();
vi.mock("../hooks/use-monthly-comparison", () => ({
  useMonthlyComparison: () => mockUseMonthlyComparison(),
}));

// Mock useCategoryBreakdown hook
const mockUseCategoryBreakdown = vi.fn();
vi.mock("../hooks/use-category-breakdown", () => ({
  useCategoryBreakdown: () => mockUseCategoryBreakdown(),
}));

// Mock useFlaggedTransactions hook
const mockUseFlaggedTransactions = vi.fn();
vi.mock("../hooks/use-flagged-transactions", () => ({
  useFlaggedTransactions: () => mockUseFlaggedTransactions(),
}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe("ProfilePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSession.mockReturnValue({
      data: { accessToken: "test-token" },
    });
    mockUseHealthScore.mockReturnValue({
      healthScore: null,
      isLoading: false,
      isError: false,
      isNotFound: true,
    });
    mockUseHealthScoreHistory.mockReturnValue({
      history: [],
      isLoading: false,
      isError: false,
    });
    mockUseMonthlyComparison.mockReturnValue({
      comparison: null,
      isLoading: false,
      isError: false,
    });
    mockUseCategoryBreakdown.mockReturnValue({
      breakdown: null,
      isLoading: false,
      isError: false,
    });
    mockUseFlaggedTransactions.mockReturnValue({
      flaggedTransactions: [],
      isLoading: false,
      isError: false,
    });
  });

  it("renders loading skeleton", () => {
    mockUseProfile.mockReturnValue({
      profile: null,
      isLoading: true,
      isError: false,
      isNotFound: false,
    });

    renderWithProviders(<ProfilePage />);
    // Skeletons render data-slot="skeleton" elements
    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders empty state when no profile exists", () => {
    mockUseProfile.mockReturnValue({
      profile: null,
      isLoading: false,
      isError: false,
      isNotFound: true,
    });

    renderWithProviders(<ProfilePage />);
    expect(screen.getByText("No financial profile yet. Upload a bank statement to get started.")).toBeTruthy();
    expect(screen.getByText("Upload Statement")).toBeTruthy();
  });

  it("renders error state", () => {
    mockUseProfile.mockReturnValue({
      profile: null,
      isLoading: false,
      isError: true,
      isNotFound: false,
    });

    renderWithProviders(<ProfilePage />);
    expect(screen.getByText("Failed to load your financial profile. Please try again.")).toBeTruthy();
  });

  it("renders profile data with formatted currency", () => {
    mockUseProfile.mockReturnValue({
      profile: {
        id: "test-id",
        totalIncome: 50000,
        totalExpenses: -20000,
        categoryTotals: { food: -15000, transport: -5000 },
        periodStart: "2026-01-01T00:00:00Z",
        periodEnd: "2026-03-31T00:00:00Z",
        updatedAt: "2026-04-01T00:00:00Z",
      },
      isLoading: false,
      isError: false,
      isNotFound: false,
    });

    renderWithProviders(<ProfilePage />);

    // Check headings exist
    expect(screen.getByText("Total Income")).toBeTruthy();
    expect(screen.getByText("Total Expenses")).toBeTruthy();
    expect(screen.getByText("Net Balance")).toBeTruthy();
    expect(screen.getAllByText("Category Breakdown").length).toBeGreaterThan(0);
  });

  it("renders health score section when score exists", () => {
    mockUseProfile.mockReturnValue({
      profile: {
        id: "test-id",
        totalIncome: 50000,
        totalExpenses: -20000,
        categoryTotals: { food: -15000, transport: -5000 },
        periodStart: "2026-01-01T00:00:00Z",
        periodEnd: "2026-03-31T00:00:00Z",
        updatedAt: "2026-04-01T00:00:00Z",
      },
      isLoading: false,
      isError: false,
      isNotFound: false,
    });
    mockUseHealthScore.mockReturnValue({
      healthScore: {
        score: 72,
        breakdown: {
          savings_ratio: 80,
          category_diversity: 65,
          expense_regularity: 70,
          income_coverage: 60,
        },
        calculatedAt: "2026-03-15T10:00:00Z",
      },
      isLoading: false,
      isError: false,
      isNotFound: false,
    });

    renderWithProviders(<ProfilePage />);

    expect(screen.getByText("Financial Health Score")).toBeTruthy();
    expect(screen.getByText("72")).toBeTruthy();
  });

  it("renders health score empty state when no score", () => {
    mockUseProfile.mockReturnValue({
      profile: {
        id: "test-id",
        totalIncome: 50000,
        totalExpenses: -20000,
        categoryTotals: { food: -15000 },
        periodStart: null,
        periodEnd: null,
        updatedAt: "2026-04-01T00:00:00Z",
      },
      isLoading: false,
      isError: false,
      isNotFound: false,
    });
    mockUseHealthScore.mockReturnValue({
      healthScore: null,
      isLoading: false,
      isError: false,
      isNotFound: true,
    });

    renderWithProviders(<ProfilePage />);

    expect(screen.getByText("Upload a statement to see your Financial Health Score")).toBeTruthy();
  });

  it("renders trend chart when history has multiple data points", () => {
    mockUseProfile.mockReturnValue({
      profile: {
        id: "test-id",
        totalIncome: 50000,
        totalExpenses: -20000,
        categoryTotals: { food: -15000 },
        periodStart: "2026-01-01T00:00:00Z",
        periodEnd: "2026-03-31T00:00:00Z",
        updatedAt: "2026-04-01T00:00:00Z",
      },
      isLoading: false,
      isError: false,
      isNotFound: false,
    });
    mockUseHealthScore.mockReturnValue({
      healthScore: {
        score: 72,
        breakdown: { savings_ratio: 80, category_diversity: 65, expense_regularity: 70, income_coverage: 60 },
        calculatedAt: "2026-03-15T10:00:00Z",
      },
      isLoading: false,
      isError: false,
      isNotFound: false,
    });
    mockUseHealthScoreHistory.mockReturnValue({
      history: [
        { score: 50, breakdown: { savings_ratio: 50, category_diversity: 50, expense_regularity: 50, income_coverage: 50 }, calculatedAt: "2026-01-15T10:00:00Z" },
        { score: 72, breakdown: { savings_ratio: 80, category_diversity: 65, expense_regularity: 70, income_coverage: 60 }, calculatedAt: "2026-03-15T10:00:00Z" },
      ],
      isLoading: false,
      isError: false,
    });

    renderWithProviders(<ProfilePage />);

    expect(screen.getByText("Score History")).toBeTruthy();
    // The trend chart SVG should be rendered with role="img"
    const svg = document.querySelector('svg[role="img"][aria-label*="Health score trend"]');
    expect(svg).toBeTruthy();
  });

  it("renders category breakdown with correct items from hook", () => {
    mockUseProfile.mockReturnValue({
      profile: {
        id: "test-id",
        totalIncome: 100000,
        totalExpenses: -45000,
        categoryTotals: {},
        periodStart: "2026-01-01T00:00:00Z",
        periodEnd: "2026-03-31T00:00:00Z",
        updatedAt: "2026-04-01T00:00:00Z",
      },
      isLoading: false,
      isError: false,
      isNotFound: false,
    });
    mockUseCategoryBreakdown.mockReturnValue({
      breakdown: {
        categories: [
          { category: "food", amount: 25000, percentage: 55.6, },
          { category: "transport", amount: 10000, percentage: 22.2, },
          { category: "entertainment", amount: 10000, percentage: 22.2, },
        ],
        totalExpenses: 45000,
      },
      isLoading: false,
      isError: false,
    });

    renderWithProviders(<ProfilePage />);

    expect(screen.getAllByText("Category Breakdown").length).toBeGreaterThan(0);
    expect(screen.getByText("Food")).toBeTruthy();
    expect(screen.getByText("Transport")).toBeTruthy();
    expect(screen.getByText("Entertainment")).toBeTruthy();
  });

  it("renders breakdown loading skeleton", () => {
    mockUseProfile.mockReturnValue({
      profile: {
        id: "test-id",
        totalIncome: 50000,
        totalExpenses: -20000,
        categoryTotals: {},
        periodStart: null,
        periodEnd: null,
        updatedAt: "2026-04-01T00:00:00Z",
      },
      isLoading: false,
      isError: false,
      isNotFound: false,
    });
    mockUseCategoryBreakdown.mockReturnValue({
      breakdown: null,
      isLoading: true,
      isError: false,
    });

    renderWithProviders(<ProfilePage />);

    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders breakdown error state", () => {
    mockUseProfile.mockReturnValue({
      profile: {
        id: "test-id",
        totalIncome: 50000,
        totalExpenses: -20000,
        categoryTotals: {},
        periodStart: null,
        periodEnd: null,
        updatedAt: "2026-04-01T00:00:00Z",
      },
      isLoading: false,
      isError: false,
      isNotFound: false,
    });
    mockUseCategoryBreakdown.mockReturnValue({
      breakdown: null,
      isLoading: false,
      isError: true,
    });

    renderWithProviders(<ProfilePage />);

    expect(screen.getByText("Failed to load spending breakdown. Please try again.")).toBeTruthy();
  });

  it("renders breakdown empty/no-data state", () => {
    mockUseProfile.mockReturnValue({
      profile: {
        id: "test-id",
        totalIncome: 50000,
        totalExpenses: 0,
        categoryTotals: {},
        periodStart: null,
        periodEnd: null,
        updatedAt: "2026-04-01T00:00:00Z",
      },
      isLoading: false,
      isError: false,
      isNotFound: false,
    });
    mockUseCategoryBreakdown.mockReturnValue({
      breakdown: { categories: [], totalExpenses: 0 },
      isLoading: false,
      isError: false,
    });

    renderWithProviders(<ProfilePage />);

    expect(screen.getByText("No spending data yet. Upload a statement to see your spending breakdown.")).toBeTruthy();
  });

  it("renders monthly comparison section when data is available", () => {
    mockUseProfile.mockReturnValue({
      profile: {
        id: "test-id",
        totalIncome: 50000,
        totalExpenses: -20000,
        categoryTotals: { food: -15000 },
        periodStart: "2026-01-01T00:00:00Z",
        periodEnd: "2026-03-31T00:00:00Z",
        updatedAt: "2026-04-01T00:00:00Z",
      },
      isLoading: false,
      isError: false,
      isNotFound: false,
    });
    mockUseMonthlyComparison.mockReturnValue({
      comparison: {
        currentMonth: "2026-03",
        previousMonth: "2026-02",
        categories: [
          { category: "food", currentAmount: 12000, previousAmount: 10000, changePercent: 20.0, changeAmount: 2000 },
          { category: "transport", currentAmount: 3000, previousAmount: 5000, changePercent: -40.0, changeAmount: -2000 },
        ],
        totalCurrent: 15000,
        totalPrevious: 15000,
        totalChangePercent: 0.0,
      },
      isLoading: false,
      isError: false,
    });

    renderWithProviders(<ProfilePage />);

    expect(screen.getByText("Month-over-Month Spending")).toBeTruthy();
    // Verify comparison-specific elements: direction arrows
    expect(screen.getByText("+20%")).toBeTruthy();
    expect(screen.getByText("-40%")).toBeTruthy();
    expect(screen.getByText("Total Spending")).toBeTruthy();
  });

  it("renders encouraging message when comparison data is null", () => {
    mockUseProfile.mockReturnValue({
      profile: {
        id: "test-id",
        totalIncome: 50000,
        totalExpenses: -20000,
        categoryTotals: { food: -15000 },
        periodStart: null,
        periodEnd: null,
        updatedAt: "2026-04-01T00:00:00Z",
      },
      isLoading: false,
      isError: false,
      isNotFound: false,
    });
    mockUseMonthlyComparison.mockReturnValue({
      comparison: null,
      isLoading: false,
      isError: false,
    });

    renderWithProviders(<ProfilePage />);

    expect(screen.getByText("Upload another month to see spending trends")).toBeTruthy();
  });

  it("renders comparison error state when fetch fails", () => {
    mockUseProfile.mockReturnValue({
      profile: {
        id: "test-id",
        totalIncome: 50000,
        totalExpenses: -20000,
        categoryTotals: { food: -15000 },
        periodStart: null,
        periodEnd: null,
        updatedAt: "2026-04-01T00:00:00Z",
      },
      isLoading: false,
      isError: false,
      isNotFound: false,
    });
    mockUseMonthlyComparison.mockReturnValue({
      comparison: null,
      isLoading: false,
      isError: true,
    });

    renderWithProviders(<ProfilePage />);

    expect(screen.getByText("Failed to load spending comparison. Please try again.")).toBeTruthy();
    // Should NOT show the encouraging "upload" message
    expect(screen.queryByText("Upload another month to see spending trends")).toBeNull();
  });

  it("renders comparison loading skeleton", () => {
    mockUseProfile.mockReturnValue({
      profile: {
        id: "test-id",
        totalIncome: 50000,
        totalExpenses: -20000,
        categoryTotals: { food: -15000 },
        periodStart: null,
        periodEnd: null,
        updatedAt: "2026-04-01T00:00:00Z",
      },
      isLoading: false,
      isError: false,
      isNotFound: false,
    });
    mockUseMonthlyComparison.mockReturnValue({
      comparison: null,
      isLoading: true,
      isError: false,
    });

    renderWithProviders(<ProfilePage />);

    // Should render skeleton placeholders for the comparison section
    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
