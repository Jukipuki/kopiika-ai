import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";

const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

import {
  useMilestoneFeedback,
  _milestoneSession,
} from "../hooks/use-milestone-feedback";

const mockFetch = vi.fn();

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

describe("useMilestoneFeedback", () => {
  beforeEach(() => {
    mockUseSession.mockReturnValue({
      data: { accessToken: "test-token" },
    });
    _milestoneSession.hasShownCard = false;
    global.fetch = mockFetch as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    mockFetch.mockReset();
    _milestoneSession.hasShownCard = false;
  });

  it("returns pending card from GET /milestone-feedback/pending", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        cards: [
          { cardType: "milestone_3rd_upload", variant: "emoji_rating" },
        ],
      }),
    });

    const { result } = renderHook(() => useMilestoneFeedback(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.pendingCard).toEqual({
        cardType: "milestone_3rd_upload",
        variant: "emoji_rating",
      });
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/milestone-feedback/pending"),
      expect.objectContaining({
        headers: { Authorization: "Bearer test-token" },
      }),
    );
  });

  it("returns null when cards array is empty", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ cards: [] }),
    });

    const { result } = renderHook(() => useMilestoneFeedback(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.pendingCard).toBeNull();
    });
  });

  it("session cap suppresses card after first show", async () => {
    _milestoneSession.hasShownCard = true;
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        cards: [
          { cardType: "milestone_3rd_upload", variant: "emoji_rating" },
        ],
      }),
    });

    const { result } = renderHook(() => useMilestoneFeedback(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      // Query settles but session cap nulls the card
      expect(mockFetch).toHaveBeenCalled();
    });
    expect(result.current.pendingCard).toBeNull();
  });

  it("submitResponse POSTs to /milestone-feedback/respond with correct body", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ cards: [] }),
    });

    const { result } = renderHook(() => useMilestoneFeedback(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.pendingCard).toBeNull());

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    });

    act(() => {
      result.current.submitResponse({
        cardType: "milestone_3rd_upload",
        responseValue: "happy",
        freeText: "nice",
      });
    });

    await waitFor(() => {
      const [url, init] = mockFetch.mock.calls.find(
        (call) =>
          typeof call[0] === "string" &&
          call[0].includes("/milestone-feedback/respond"),
      )!;
      expect(url).toContain("/api/v1/milestone-feedback/respond");
      expect(init.method).toBe("POST");
      const body = JSON.parse(init.body as string);
      expect(body).toEqual({
        cardType: "milestone_3rd_upload",
        responseValue: "happy",
        freeText: "nice",
      });
    });
  });

  it("sets session cap and invalidates query on successful submit", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        cards: [
          { cardType: "milestone_3rd_upload", variant: "emoji_rating" },
        ],
      }),
    });

    const { result } = renderHook(() => useMilestoneFeedback(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.pendingCard).not.toBeNull();
    });

    // POST succeeds
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    });
    // Invalidation refetch returns fresh (empty) cards
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ cards: [] }),
    });

    act(() => {
      result.current.submitResponse({
        cardType: "milestone_3rd_upload",
        responseValue: "dismissed",
      });
    });

    await waitFor(() => {
      expect(_milestoneSession.hasShownCard).toBe(true);
    });
  });
});
