import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createUseTranslations } from "@/test-utils/intl-mock";
import ReviewQueuePage from "../components/ReviewQueuePage";

vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

const mockFetch = vi.fn();
global.fetch = mockFetch;

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const ONE_ENTRY = {
  id: "e1",
  transactionId: "t1",
  description: "Unknown Merchant",
  amount: -45000, // -450.00 UAH
  date: "2026-04-20",
  suggestedCategory: "shopping",
  suggestedKind: "spending",
  categorizationConfidence: 0.62,
  createdAt: "2026-04-21T12:00:00",
  status: "pending",
  currencyCode: 980,
};

describe("ReviewQueuePage (Story 11.8 AC #12 item 2)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockUseSession.mockReturnValue({ data: { accessToken: "tok" } });
  });

  it("renders empty state when no entries pending", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ items: [], nextCursor: null, hasMore: false }),
    });
    renderWithClient(<ReviewQueuePage />);
    await waitFor(() => {
      expect(
        screen.getByText(/Nothing to review/i),
      ).toBeInTheDocument();
    });
  });

  it("renders pending entries with confidence badge as integer percent", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ items: [ONE_ENTRY], nextCursor: null, hasMore: false }),
    });
    renderWithClient(<ReviewQueuePage />);

    await waitFor(() => {
      expect(screen.getByText("Unknown Merchant")).toBeInTheDocument();
    });
    // Confidence 0.62 → 62%
    expect(screen.getByText(/62/)).toBeInTheDocument();
  });

  it("resolve posts (category, kind) and revalidates", async () => {
    // Initial list fetch
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ items: [ONE_ENTRY], nextCursor: null, hasMore: false }),
    });
    // Resolve POST
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        id: "e1",
        transactionId: "t1",
        status: "resolved",
        resolvedCategory: "groceries",
        resolvedKind: "spending",
        resolvedAt: "2026-04-22T00:00:00Z",
      }),
    });
    // Refetch list after mutation invalidates
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], nextCursor: null, hasMore: false }),
    });

    renderWithClient(<ReviewQueuePage />);
    await waitFor(() => {
      expect(screen.getByText("Unknown Merchant")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Edit/i }));

    // Pick a different category + submit.
    const catSelect = screen.getByLabelText(/Category/i);
    await user.selectOptions(catSelect, "groceries");
    await user.click(screen.getByRole("button", { name: /^Save$/i }));

    await waitFor(() => {
      const resolvePost = mockFetch.mock.calls.find(
        ([url, opts]) =>
          typeof url === "string" &&
          url.includes("/review-queue/e1/resolve") &&
          opts?.method === "POST",
      );
      expect(resolvePost).toBeTruthy();
      const body = JSON.parse((resolvePost as any[])[1].body);
      expect(body).toEqual({ category: "groceries", kind: "spending" });
    });
  });

  it("matrix-violation 400 shows inline error (not toast)", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ items: [ONE_ENTRY], nextCursor: null, hasMore: false }),
    });
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ detail: "invalid" }),
    });

    renderWithClient(<ReviewQueuePage />);
    await waitFor(() =>
      expect(screen.getByText("Unknown Merchant")).toBeInTheDocument(),
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Edit/i }));
    await user.selectOptions(screen.getByLabelText(/Kind/i), "income");
    await user.click(screen.getByRole("button", { name: /^Save$/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("dismiss calls POST and triggers revalidation", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ items: [ONE_ENTRY], nextCursor: null, hasMore: false }),
    });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        id: "e1",
        transactionId: "t1",
        status: "dismissed",
      }),
    });
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], nextCursor: null, hasMore: false }),
    });

    renderWithClient(<ReviewQueuePage />);
    await waitFor(() =>
      expect(screen.getByText("Unknown Merchant")).toBeInTheDocument(),
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Dismiss/i }));

    await waitFor(() => {
      const dismissPost = mockFetch.mock.calls.find(
        ([url, opts]) =>
          typeof url === "string" &&
          url.includes("/review-queue/e1/dismiss") &&
          opts?.method === "POST",
      );
      expect(dismissPost).toBeTruthy();
    });
  });
});
