import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  useCardInteractions,
  setPendingSwipeDirection,
  __resetCardInteractionsForTesting,
  __getPendingBatchForTesting,
} from "../hooks/use-card-interactions";

const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

const mockFetch = vi.fn();

describe("useCardInteractions", () => {
  let nowValue: number;

  beforeEach(() => {
    mockUseSession.mockReturnValue({ data: { accessToken: "test-token" } });
    mockFetch.mockResolvedValue({ ok: true });
    global.fetch = mockFetch as unknown as typeof fetch;

    nowValue = 1000;
    vi.spyOn(performance, "now").mockImplementation(() => nowValue);

    __resetCardInteractionsForTesting();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    mockFetch.mockReset();
  });

  it("captures time_on_card_ms from mount to unmount via performance.now", () => {
    const { unmount } = renderHook(() => useCardInteractions("card-1", 0));
    nowValue = 1000 + 5_000;
    unmount();

    const batch = __getPendingBatchForTesting();
    expect(batch).toHaveLength(1);
    expect(batch[0].cardId).toBe("card-1");
    expect(batch[0].timeOnCardMs).toBe(5_000);
  });

  it("captures education expansion state and max depth via onEducationExpanded", () => {
    const { result, unmount } = renderHook(() => useCardInteractions("card-2", 0));
    act(() => {
      result.current.onEducationExpanded(1);
      result.current.onEducationExpanded(2);
    });
    unmount();

    const batch = __getPendingBatchForTesting();
    expect(batch[0].educationExpanded).toBe(true);
    expect(batch[0].educationDepthReached).toBe(2);
  });

  it("defaults swipe_direction to 'none' when no pending direction was set", () => {
    const { unmount } = renderHook(() => useCardInteractions("card-3", 2));
    unmount();

    const batch = __getPendingBatchForTesting();
    expect(batch[0].swipeDirection).toBe("none");
    expect(batch[0].cardPositionInFeed).toBe(2);
  });

  it("consumes setPendingSwipeDirection set before unmount", () => {
    const { unmount } = renderHook(() => useCardInteractions("card-4", 1));
    setPendingSwipeDirection("card-4", "right");
    unmount();

    const batch = __getPendingBatchForTesting();
    expect(batch[0].swipeDirection).toBe("right");
  });

  it("does not flush until threshold of 5 interactions is reached", () => {
    for (let i = 0; i < 4; i++) {
      const { unmount } = renderHook(() =>
        useCardInteractions(`card-flush-${i}`, i),
      );
      unmount();
    }
    expect(mockFetch).not.toHaveBeenCalled();
    expect(__getPendingBatchForTesting()).toHaveLength(4);
  });

  it("flushes via fetch when batch reaches 5", () => {
    for (let i = 0; i < 5; i++) {
      const { unmount } = renderHook(() =>
        useCardInteractions(`card-flush-${i}`, i),
      );
      unmount();
    }
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer test-token",
    );
    const body = JSON.parse(init.body as string) as {
      interactions: { cardId: string }[];
    };
    expect(body.interactions).toHaveLength(5);
    expect(__getPendingBatchForTesting()).toHaveLength(0);
  });

  it("flushes pending batch via fetch keepalive on beforeunload", () => {
    const { unmount } = renderHook(() => useCardInteractions("card-beacon", 0));
    unmount();
    expect(__getPendingBatchForTesting()).toHaveLength(1);

    window.dispatchEvent(new Event("beforeunload"));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(init.keepalive).toBe(true);
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer test-token",
    );
    expect(__getPendingBatchForTesting()).toHaveLength(0);
  });

  it("keeps records queued when no access token is available", () => {
    mockUseSession.mockReturnValue({ data: null });
    for (let i = 0; i < 5; i++) {
      const { unmount } = renderHook(() =>
        useCardInteractions(`card-noauth-${i}`, i),
      );
      unmount();
    }
    expect(mockFetch).not.toHaveBeenCalled();
    // Records remain in the batch for later flush when auth becomes available
    expect(__getPendingBatchForTesting()).toHaveLength(5);
  });
});
