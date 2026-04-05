import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useTeachingFeed } from "../hooks/use-teaching-feed";
import type { InsightCard } from "../types";

// Mock next-auth/react
const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

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
];

const mockItems2: InsightCard[] = [
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

describe("useTeachingFeed", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSession.mockReturnValue({ data: { accessToken: "test-token" } });
  });

  it("returns loading state initially", () => {
    mockFetch.mockReturnValue(new Promise(() => {})); // never resolves
    const { result } = renderHook(() => useTeachingFeed(), { wrapper: createWrapper() });
    expect(result.current.isLoading).toBe(true);
    expect(result.current.cards).toEqual([]);
  });

  it("returns flattened cards on success (hasMore=false)", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ items: mockItems, total: 1, nextCursor: null, hasMore: false }),
    });

    const { result } = renderHook(() => useTeachingFeed(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.cards).toEqual(mockItems);
    expect(result.current.isError).toBe(false);
  });

  it("returns hasNextPage=false when hasMore=false", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ items: mockItems, total: 1, nextCursor: null, hasMore: false }),
    });

    const { result } = renderHook(() => useTeachingFeed(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasNextPage).toBe(false);
  });

  it("returns hasNextPage=true when hasMore=true", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ items: mockItems, total: 2, nextCursor: "uuid-1", hasMore: true }),
    });

    const { result } = renderHook(() => useTeachingFeed(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasNextPage).toBe(true);
  });

  it("deduplicates cards with the same id across pages", async () => {
    // First call returns page 1 with uuid-1 (hasMore=true)
    // Second call (fetchNextPage) returns page 2 with uuid-1 again + uuid-2
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({ items: mockItems, total: 2, nextCursor: "uuid-1", hasMore: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            items: [...mockItems, ...mockItems2],
            total: 2,
            nextCursor: null,
            hasMore: false,
          }),
      });

    const { result } = renderHook(() => useTeachingFeed(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    // Fetch next page
    await result.current.fetchNextPage();
    await waitFor(() => expect(result.current.isFetchingNextPage).toBe(false));

    // uuid-1 should appear only once despite being in both pages
    const ids = result.current.cards.map((c) => c.id);
    const uniqueIds = new Set(ids);
    expect(uniqueIds.size).toBe(ids.length);
    expect(result.current.cards).toHaveLength(2);
  });

  it("returns error state on fetch failure", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
    });

    const { result } = renderHook(() => useTeachingFeed(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.cards).toEqual([]);
  });

  it("does not fetch when no access token", () => {
    mockUseSession.mockReturnValue({ data: null });
    renderHook(() => useTeachingFeed(), { wrapper: createWrapper() });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("sends Authorization header with Bearer token and pageSize param", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ items: mockItems, total: 1, nextCursor: null, hasMore: false }),
    });

    const { result } = renderHook(() => useTeachingFeed(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/insights"),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      }),
    );
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("pageSize=20"),
      expect.anything(),
    );
  });
});
