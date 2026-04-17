import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";

const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

import { useCardFeedback } from "../hooks/use-card-feedback";

const mockFetch = vi.fn();

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

describe("useCardFeedback", () => {
  beforeEach(() => {
    mockUseSession.mockReturnValue({
      data: { accessToken: "test-token" },
    });
    mockFetch.mockResolvedValue({ ok: true, status: 200, json: async () => null });
    global.fetch = mockFetch as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    mockFetch.mockReset();
  });

  it("fetches card feedback on mount when authenticated", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ vote: "up", reasonChip: null, createdAt: "2026-04-17T00:00:00Z" }),
    });

    const { result } = renderHook(() => useCardFeedback("card-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.vote).toBe("up");
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/feedback/cards/card-1"),
      expect.objectContaining({
        headers: { Authorization: "Bearer test-token" },
      }),
    );
  });

  it("handles 404 as null vote (no error)", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => null,
    });

    const { result } = renderHook(() => useCardFeedback("card-2"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.vote).toBeNull();
    });
  });

  it("calls POST on submitVote", async () => {
    // Initial GET returns 404
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404, json: async () => null });

    const { result } = renderHook(() => useCardFeedback("card-3"), {
      wrapper: createWrapper(),
    });

    // Wait for query to settle
    await waitFor(() => expect(result.current.vote).toBeNull());

    // POST succeeds
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ id: "uuid", cardId: "card-3", vote: "down", createdAt: "2026-04-17T00:00:00Z" }),
    });

    act(() => {
      result.current.submitVote("down");
    });

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/feedback/cards/card-3/vote"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ vote: "down" }),
        }),
      );
    });
  });

  it("applies optimistic update on mutate", async () => {
    // Initial GET returns 404
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404, json: async () => null });

    const { result } = renderHook(() => useCardFeedback("card-4"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.vote).toBeNull());

    // POST - slow response
    mockFetch.mockImplementationOnce(
      () => new Promise((resolve) => setTimeout(() => resolve({ ok: true, status: 201, json: async () => ({}) }), 500)),
    );

    act(() => {
      result.current.submitVote("up");
    });

    // Optimistic update should be immediate
    await waitFor(() => {
      expect(result.current.vote).toBe("up");
    });
  });
});
