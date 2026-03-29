import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useUploadHistory } from "../hooks/use-upload-history";

// Mock next-auth/react
const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

function createWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

const MOCK_PAGE_1 = {
  items: [
    {
      id: "upload-1",
      fileName: "monobank_feb.csv",
      detectedFormat: "monobank",
      createdAt: "2026-03-29T10:00:00Z",
      transactionCount: 245,
      duplicatesSkipped: 0,
      status: "completed",
    },
  ],
  total: 2,
  nextCursor: "upload-1",
  hasMore: true,
};

const MOCK_PAGE_2 = {
  items: [
    {
      id: "upload-2",
      fileName: "monobank_jan.csv",
      detectedFormat: "monobank",
      createdAt: "2026-03-28T10:00:00Z",
      transactionCount: 180,
      duplicatesSkipped: 12,
      status: "completed",
    },
  ],
  total: 2,
  nextCursor: null,
  hasMore: false,
};

const MOCK_SINGLE_PAGE = {
  items: [MOCK_PAGE_1.items[0], MOCK_PAGE_2.items[0]],
  total: 2,
  nextCursor: null,
  hasMore: false,
};

describe("useUploadHistory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSession.mockReturnValue({
      data: { accessToken: "test-token" },
      status: "authenticated",
    });
  });

  it("9.1: fetches and returns upload list", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_SINGLE_PAGE),
    });

    const { result } = renderHook(() => useUploadHistory(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.uploads).toHaveLength(2);
    expect(result.current.total).toBe(2);
    expect(result.current.hasMore).toBe(false);
    expect(result.current.error).toBeNull();

    // Verify correct API call
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/uploads"),
      expect.objectContaining({
        headers: { Authorization: "Bearer test-token" },
      }),
    );
  });

  it("handles fetch error gracefully", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500 });

    const { result } = renderHook(() => useUploadHistory(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).toBe("Failed to fetch upload history");
    expect(result.current.uploads).toHaveLength(0);
  });

  it("does not fetch without session token", async () => {
    mockUseSession.mockReturnValue({ data: null, status: "unauthenticated" });

    renderHook(() => useUploadHistory(), { wrapper: createWrapper() });

    // No fetch should be made when no token
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("supports load more (infinite query pagination)", async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(MOCK_PAGE_1) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(MOCK_PAGE_2) });

    const { result } = renderHook(() => useUploadHistory(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.uploads).toHaveLength(1));
    expect(result.current.hasMore).toBe(true);

    result.current.loadMore();

    await waitFor(() => expect(result.current.uploads).toHaveLength(2));
    expect(result.current.hasMore).toBe(false);
  });

  it("refresh refetches the data", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_SINGLE_PAGE),
    });

    const { result } = renderHook(() => useUploadHistory(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.uploads).toHaveLength(2));

    expect(typeof result.current.refresh).toBe("function");
    // Calling refresh should trigger a refetch
    result.current.refresh();
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
  });
});
