import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createUseTranslations } from "@/test-utils/intl-mock";
import MyDataSection from "../components/MyDataSection";

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

// Mock next-auth/react
const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

const mockDataSummary = {
  uploadCount: 3,
  transactionCount: 125,
  transactionDateRange: {
    earliest: "2026-01-15T00:00:00",
    latest: "2026-03-20T00:00:00",
  },
  categoriesDetected: ["groceries", "transport", "entertainment"],
  insightCount: 8,
  financialProfile: {
    totalIncome: 100000,
    totalExpenses: 70000,
    categoryTotals: { groceries: 30000, transport: 20000 },
  },
  healthScoreHistory: [
    { score: 72, calculatedAt: "2026-02-01T00:00:00" },
    { score: 78, calculatedAt: "2026-03-01T00:00:00" },
  ],
  consentRecords: [
    { consentType: "ai_processing", grantedAt: "2026-01-01T00:00:00" },
  ],
};

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("MyDataSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSession.mockReturnValue({
      data: { accessToken: "test-token" },
      status: "authenticated",
    });
  });

  it("renders loading skeleton while fetching", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    renderWithQuery(<MyDataSection />);

    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders all stats from API response", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDataSummary),
    });

    renderWithQuery(<MyDataSection />);

    // Wait for data to load (not just the heading which appears in skeleton too)
    await waitFor(() => {
      expect(screen.getByText("3")).toBeInTheDocument();
    });
    expect(screen.getByText("125")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();

    // Categories
    expect(screen.getByText("groceries, transport, entertainment")).toBeInTheDocument();

    // Date range
    expect(screen.getByText(/January 15, 2026/)).toBeInTheDocument();

    // Health scores - mock replaces ICU plural with raw count value
    expect(screen.getByText("Health Score History")).toBeInTheDocument();

    // Consent
    expect(screen.getByText(/ai_processing/)).toBeInTheDocument();

    // Financial profile - shows income and expenses
    expect(screen.getByText("Income")).toBeInTheDocument();
    expect(screen.getByText("Expenses")).toBeInTheDocument();
  });

  it("renders empty state for new user", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        uploadCount: 0,
        transactionCount: 0,
        transactionDateRange: null,
        categoriesDetected: [],
        insightCount: 0,
        financialProfile: null,
        healthScoreHistory: [],
        consentRecords: [],
      }),
    });

    renderWithQuery(<MyDataSection />);

    await waitFor(() => {
      expect(screen.getByText("No data yet. Upload a bank statement to get started.")).toBeInTheDocument();
    });

    const zeros = screen.getAllByText("0");
    expect(zeros.length).toBe(3); // uploads, transactions, insights all zero
  });

  it("renders error state with retry", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500 });

    renderWithQuery(<MyDataSection />);

    await waitFor(() => {
      expect(screen.getByText("Unable to connect to the server. Please try again.")).toBeInTheDocument();
    });

    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("retries fetch on retry button click", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 500 });

    renderWithQuery(<MyDataSection />);

    await waitFor(() => {
      expect(screen.getByText("Retry")).toBeInTheDocument();
    });

    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDataSummary),
    });

    const user = userEvent.setup();
    await user.click(screen.getByText("Retry"));

    await waitFor(() => {
      expect(screen.getByText("My Data")).toBeInTheDocument();
      expect(screen.getByText("3")).toBeInTheDocument();
    });
  });
});
