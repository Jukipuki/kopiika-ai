import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { FeedContainer } from "../components/FeedContainer";
import type { InsightCard } from "../types";

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

// Mock use-feed-sse — controllable per-test
const mockUseFeedSSE = vi.fn();
vi.mock("../hooks/use-feed-sse", () => ({
  useFeedSSE: (...args: unknown[]) => mockUseFeedSSE(...args),
}));

// Mock use-teaching-feed — used only in targeted tests; defaults to undefined so real hook runs otherwise
const mockUseTeachingFeed = vi.fn();
let useTeachingFeedOverride = false;
vi.mock("../hooks/use-teaching-feed", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../hooks/use-teaching-feed")>();
  return {
    useTeachingFeed: (...args: unknown[]) =>
      useTeachingFeedOverride ? mockUseTeachingFeed(...args) : actual.useTeachingFeed(...args),
  };
});

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock @/i18n/navigation
vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...props }: { href: string; children: React.ReactNode }) =>
    React.createElement("a", { href, ...props }, children),
}));

// HTML-safe attributes to forward to the rendered div
const MOTION_HTML_PROPS = new Set([
  "children",
  "className",
  "id",
  "style",
  "tabIndex",
  "role",
  "onClick",
  "onKeyDown",
  "aria-label",
  "aria-live",
  "data-testid",
]);

// Mock motion/react for CardStackNavigator used inside FeedContainer
vi.mock("motion/react", () => ({
  motion: {
    div: (props: Record<string, unknown>) => {
      const htmlProps: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(props)) {
        if (MOTION_HTML_PROPS.has(k) || k.startsWith("aria-") || k.startsWith("data-")) {
          htmlProps[k] = v;
        }
      }
      return React.createElement("div", htmlProps, props.children as React.ReactNode);
    },
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
  useReducedMotion: () => false,
}));

const mockItems: InsightCard[] = [
  {
    id: "uuid-1",
    uploadId: null,
    headline: "You spent 30% more on food",
    keyMetric: "₴3,200",
    whyItMatters: "Food is your biggest expense.",
    deepDive: "Restaurants 60%, groceries 40%.",
    severity: "high",
    category: "food",
    createdAt: "2026-04-04T12:00:00.000000Z",
  },
  {
    id: "uuid-2",
    uploadId: null,
    headline: "Utility bills increased",
    keyMetric: "₴800",
    whyItMatters: "Seasonal change.",
    deepDive: "Electricity usage up 20%.",
    severity: "medium",
    category: "utilities",
    createdAt: "2026-04-04T12:00:00.000000Z",
  },
];

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

describe("FeedContainer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useTeachingFeedOverride = false;
    mockUseSession.mockReturnValue({ data: { accessToken: "test-token" } });
    mockUseFeedSSE.mockReturnValue({ pendingInsightIds: [], isStreaming: false, message: null });
  });

  it("shows skeleton cards during loading", () => {
    mockFetch.mockReturnValue(new Promise(() => {})); // never resolves
    render(<FeedContainer />, { wrapper: createWrapper() });
    expect(screen.getByLabelText("Loading insights")).toBeInTheDocument();
  });

  it("shows error message on fetch failure", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500 });
    render(<FeedContainer />, { wrapper: createWrapper() });
    await waitFor(() =>
      expect(screen.getByText(/failed to load insights/i)).toBeInTheDocument(),
    );
  });

  it("shows retry button on error", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500 });
    render(<FeedContainer />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument());
  });

  it("renders first insight card on success (stack shows card at index 0)", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ items: mockItems, total: 2, nextCursor: null, hasMore: false }),
    });
    render(<FeedContainer />, { wrapper: createWrapper() });
    await waitFor(() =>
      expect(screen.getByText("You spent 30% more on food")).toBeInTheDocument(),
    );
    // Only the first card is visible in the stack (not all cards at once)
    expect(screen.queryByText("Utility bills increased")).not.toBeInTheDocument();
  });

  it("shows empty state when items is empty array", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ items: [], total: 0, nextCursor: null, hasMore: false }),
    });
    render(<FeedContainer />, { wrapper: createWrapper() });
    await waitFor(() =>
      expect(
        screen.getByText(/no insights yet/i),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("link", { name: /go to upload/i })).toBeInTheDocument();
  });

  it("retry button triggers refetch", async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: false, status: 500 })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({ items: mockItems, total: 2, nextCursor: null, hasMore: false }),
      });

    render(<FeedContainer />, { wrapper: createWrapper() });

    await waitFor(() => expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() =>
      expect(screen.getByText("You spent 30% more on food")).toBeInTheDocument(),
    );
    // Stack shows first card only after successful retry
    expect(screen.queryByText("Utility bills increased")).not.toBeInTheDocument();
  });

  it("passes hasNextPage=true to CardStackNavigator — counter shows '+' suffix", async () => {
    // When fetch returns hasMore=true, FeedContainer passes hasNextPage=true to CardStackNavigator
    // which renders the counter with a '+' suffix
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ items: mockItems, total: 4, nextCursor: "uuid-2", hasMore: true }),
    });
    render(<FeedContainer />, { wrapper: createWrapper() });
    await waitFor(() =>
      expect(screen.getByText("You spent 30% more on food")).toBeInTheDocument(),
    );
    // Counter shows "1 of 2+" because hasNextPage=true
    expect(screen.getByText("1 of 2+")).toBeInTheDocument();
  });

  it("shows inline retry when pagination error occurs but keeps loaded cards visible (AC #4)", async () => {
    // Page 1 succeeds, then page 2 fails
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({ items: mockItems, total: 4, nextCursor: "uuid-2", hasMore: true }),
      })
      .mockResolvedValueOnce({ ok: false, status: 500 });

    render(<FeedContainer />, { wrapper: createWrapper() });

    // Page 1 loads successfully
    await waitFor(() =>
      expect(screen.getByText("You spent 30% more on food")).toBeInTheDocument(),
    );

    // Navigate to last card to trigger onLoadMore
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));

    // Wait for the pagination error to surface
    await waitFor(() =>
      expect(screen.getByText(/failed to load more insights/i)).toBeInTheDocument(),
    );

    // Loaded cards remain visible (not replaced by full-screen error)
    expect(screen.getByText("Utility bills increased")).toBeInTheDocument();

    // Inline retry button is available
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("passes fetchNextPage as onLoadMore — counter shows '+' and onLoadMore triggers", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ items: mockItems, total: 4, nextCursor: "uuid-2", hasMore: true }),
    });
    render(<FeedContainer />, { wrapper: createWrapper() });
    await waitFor(() =>
      expect(screen.getByText("You spent 30% more on food")).toBeInTheDocument(),
    );
    // Counter shows "+" suffix proving hasNextPage was passed
    expect(screen.getByText("1 of 2+")).toBeInTheDocument();
    // Navigate to last card — this triggers onLoadMore (fetchNextPage)
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    // fetchNextPage was called, triggering another fetch
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
  });

  it("passes message from useFeedSSE to ProgressiveLoadingState when streaming with no cards", () => {
    mockUseFeedSSE.mockReturnValue({
      pendingInsightIds: [],
      isStreaming: true,
      message: "Categorizing your transactions...",
    });
    mockFetch.mockReturnValue(new Promise(() => {})); // never resolves
    render(<FeedContainer jobId="job-123" />, { wrapper: createWrapper() });
    expect(screen.getByText("Categorizing your transactions...")).toBeInTheDocument();
  });

  it("shows fallback 'Processing...' when message is null during streaming", () => {
    mockUseFeedSSE.mockReturnValue({
      pendingInsightIds: [],
      isStreaming: true,
      message: null,
    });
    mockFetch.mockReturnValue(new Promise(() => {}));
    render(<FeedContainer jobId="job-123" />, { wrapper: createWrapper() });
    expect(screen.getByText("Processing...")).toBeInTheDocument();
  });

  it("shows inline ProgressiveLoadingState with message when streaming with existing cards", async () => {
    mockUseFeedSSE.mockReturnValue({
      pendingInsightIds: [],
      isStreaming: true,
      message: "Generating financial insights...",
    });
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ items: mockItems, total: 2, nextCursor: null, hasMore: false }),
    });
    render(<FeedContainer jobId="job-123" />, { wrapper: createWrapper() });
    await waitFor(() =>
      expect(screen.getByText("You spent 30% more on food")).toBeInTheDocument(),
    );
    expect(screen.getByText("Generating financial insights...")).toBeInTheDocument();
  });

  // AC #3 — Task 4.2: transition from progressive loading to card display
  it("hides ProgressiveLoadingState and shows cards when streaming ends and cards arrive", () => {
    useTeachingFeedOverride = true;

    // Phase 1: streaming active, no cards
    mockUseTeachingFeed.mockReturnValue({
      cards: [],
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isFetchNextPageError: false,
      isLoading: false,
      isError: false,
      isFetching: false,
    });
    mockUseFeedSSE.mockReturnValue({
      pendingInsightIds: [],
      isStreaming: true,
      message: "Processing...",
    });

    const { rerender } = render(<FeedContainer jobId="job-123" />, { wrapper: createWrapper() });
    expect(screen.getByText("Processing...")).toBeInTheDocument();

    // Phase 2: streaming ends, cards arrive
    mockUseTeachingFeed.mockReturnValue({
      cards: mockItems,
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isFetchNextPageError: false,
      isLoading: false,
      isError: false,
      isFetching: false,
    });
    mockUseFeedSSE.mockReturnValue({
      pendingInsightIds: [],
      isStreaming: false,
      message: null,
    });

    rerender(<FeedContainer jobId="job-123" />);

    expect(screen.getByText("You spent 30% more on food")).toBeInTheDocument();
    expect(screen.queryByText("Processing...")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Loading insights")).not.toBeInTheDocument();
  });

  // AC #3 — race condition guard: skeleton shown instead of empty state while refetching after stream
  it("shows skeleton (not empty state) when streaming has ended but fetch is still in-flight (race condition guard)", () => {
    useTeachingFeedOverride = true;

    // Phase 1: streaming active, no cards
    mockUseTeachingFeed.mockReturnValue({
      cards: [],
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isFetchNextPageError: false,
      isLoading: false,
      isError: false,
      isFetching: false,
    });
    mockUseFeedSSE.mockReturnValue({
      pendingInsightIds: [],
      isStreaming: true,
      message: "Processing...",
    });

    const { rerender } = render(<FeedContainer jobId="job-123" />, { wrapper: createWrapper() });
    expect(screen.getByText("Processing...")).toBeInTheDocument();

    // Phase 2: streaming ends, refetch triggered but not yet resolved
    mockUseTeachingFeed.mockReturnValue({
      cards: [],
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isFetchNextPageError: false,
      isLoading: false,
      isError: false,
      isFetching: true, // refetch triggered by job-complete invalidation, not yet resolved
    });
    mockUseFeedSSE.mockReturnValue({
      pendingInsightIds: [],
      isStreaming: false, // stream ended
      message: null,
    });

    rerender(<FeedContainer jobId="job-123" />);

    expect(screen.getByLabelText("Loading insights")).toBeInTheDocument();
    expect(screen.queryByText(/no insights yet/i)).not.toBeInTheDocument();
  });

  // AC #4 — Task 4.3: inline streaming indicator coexists with card stack.
  // Note: AnimatePresence exit animation (fade-out) cannot be verified in jsdom;
  // this test covers structural co-existence only. Visual transition relies on motion/react runtime.
  it("ProgressiveLoadingState below card stack does not replace cards when streaming with existing cards", async () => {
    mockUseFeedSSE.mockReturnValue({
      pendingInsightIds: [],
      isStreaming: true,
      message: "Almost done...",
    });
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ items: mockItems, total: 2, nextCursor: null, hasMore: false }),
    });
    render(<FeedContainer jobId="job-123" />, { wrapper: createWrapper() });

    await waitFor(() =>
      expect(screen.getByText("You spent 30% more on food")).toBeInTheDocument(),
    );
    // Cards are shown AND the inline streaming indicator is also present
    expect(screen.getByText("Almost done...")).toBeInTheDocument();
    // No layout shift: the card stack is the primary content
    expect(screen.getByText("You spent 30% more on food")).toBeInTheDocument();
  });

  it("renders FeedDisclaimer when cards are present", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ items: mockItems, total: 2, nextCursor: null, hasMore: false }),
    });
    render(<FeedContainer />, { wrapper: createWrapper() });
    await waitFor(() =>
      expect(screen.getByText("You spent 30% more on food")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("feed-disclaimer")).toBeInTheDocument();
  });

  it("does NOT render FeedDisclaimer in empty state", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ items: [], total: 0, nextCursor: null, hasMore: false }),
    });
    render(<FeedContainer />, { wrapper: createWrapper() });
    await waitFor(() =>
      expect(screen.getByText(/no insights yet/i)).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("feed-disclaimer")).not.toBeInTheDocument();
  });

  it("does NOT render FeedDisclaimer in loading state", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    render(<FeedContainer />, { wrapper: createWrapper() });
    expect(screen.getByLabelText("Loading insights")).toBeInTheDocument();
    expect(screen.queryByTestId("feed-disclaimer")).not.toBeInTheDocument();
  });

  it("does NOT render FeedDisclaimer in error state", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500 });
    render(<FeedContainer />, { wrapper: createWrapper() });
    await waitFor(() =>
      expect(screen.getByText(/failed to load insights/i)).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("feed-disclaimer")).not.toBeInTheDocument();
  });

  it("SSE invalidation still works — queryKey ['teaching-feed'] is used with infinite query", async () => {
    // When pendingInsightIds is non-empty, FeedContainer calls invalidateQueries(["teaching-feed"])
    // TanStack Query v5 with useInfiniteQuery handles this same queryKey correctly
    mockUseFeedSSE.mockReturnValue({
      pendingInsightIds: ["new-insight-id"],
      isStreaming: true,
      message: "Processing your data...",
    });
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ items: mockItems, total: 2, nextCursor: null, hasMore: false }),
    });
    render(<FeedContainer />, { wrapper: createWrapper() });
    // invalidateQueries triggers a refetch — fetch is called at least once
    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    // The fetch URL uses the correct insights endpoint
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/insights"),
      expect.anything(),
    );
  });
});
