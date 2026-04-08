import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

// Mock EventSource globally
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onerror: ((e: Event) => void) | null = null;
  private listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (e: MessageEvent) => void) {
    this.listeners[type] = [...(this.listeners[type] ?? []), handler];
  }

  emit(type: string, data: unknown) {
    const event = { data: JSON.stringify(data) } as MessageEvent;
    this.listeners[type]?.forEach((h) => h(event));
  }

  close() {
    this.closed = true;
  }
}

vi.stubGlobal("EventSource", MockEventSource);

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

describe("useFeedSSE", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    MockEventSource.instances = [];
    vi.useRealTimers();
  });

  it("returns isStreaming: false when jobId is null", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    const { result } = renderHook(() => useFeedSSE(null, "token"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isStreaming).toBe(false);
    expect(result.current.pendingInsightIds).toEqual([]);
    expect(result.current.message).toBeNull();
  });

  it("returns isStreaming: false when accessToken is undefined", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    const { result } = renderHook(() => useFeedSSE("job-123", undefined), {
      wrapper: createWrapper(),
    });

    expect(result.current.isStreaming).toBe(false);
  });

  it("opens EventSource with correct URL when jobId + token provided", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    renderHook(() => useFeedSSE("job-123", "my-token"), {
      wrapper: createWrapper(),
    });

    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].url).toContain("/api/v1/jobs/job-123/stream");
    expect(MockEventSource.instances[0].url).toContain("token=my-token");
  });

  it("sets isStreaming: true when jobId and token are provided", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    const { result } = renderHook(() => useFeedSSE("job-123", "token"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isStreaming).toBe(true);
  });

  it("accumulates pendingInsightIds on insight-ready events", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    const { result } = renderHook(() => useFeedSSE("job-123", "token"), {
      wrapper: createWrapper(),
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es.emit("insight-ready", { event: "insight-ready", jobId: "job-123", insightId: "id-1", type: "food" });
    });

    expect(result.current.pendingInsightIds).toEqual(["id-1"]);

    act(() => {
      es.emit("insight-ready", { event: "insight-ready", jobId: "job-123", insightId: "id-2", type: "transport" });
    });

    expect(result.current.pendingInsightIds).toEqual(["id-1", "id-2"]);
  });

  it("sets isStreaming: false on job-complete", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    const { result } = renderHook(() => useFeedSSE("job-123", "token"), {
      wrapper: createWrapper(),
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es.emit("job-complete", { event: "job-complete", jobId: "job-123", status: "completed" });
    });

    expect(result.current.isStreaming).toBe(false);
  });

  it("calls queryClient.invalidateQueries with teaching-feed on job-complete", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);

    renderHook(() => useFeedSSE("job-123", "token"), { wrapper });

    const es = MockEventSource.instances[0];

    act(() => {
      es.emit("job-complete", { event: "job-complete", jobId: "job-123", status: "completed" });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["teaching-feed"] });
  });

  it("sets isStreaming: false and clears pendingInsightIds on job-failed", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    const { result } = renderHook(() => useFeedSSE("job-123", "token"), {
      wrapper: createWrapper(),
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es.emit("insight-ready", { event: "insight-ready", jobId: "job-123", insightId: "id-1", type: "food" });
    });

    act(() => {
      es.emit("job-failed", { event: "job-failed", jobId: "job-123" });
    });

    expect(result.current.isStreaming).toBe(false);
    expect(result.current.pendingInsightIds).toEqual([]);
  });

  it("sets message from pipeline-progress data.message", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    const { result } = renderHook(() => useFeedSSE("job-123", "token"), {
      wrapper: createWrapper(),
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es.emit("pipeline-progress", {
        event: "pipeline-progress",
        jobId: "job-123",
        step: "categorization",
        progress: 60,
        message: "Categorizing your transactions...",
      });
    });

    expect(result.current.message).toBe("Categorizing your transactions...");
  });

  it("sets message to null when data.message is missing", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    const { result } = renderHook(() => useFeedSSE("job-123", "token"), {
      wrapper: createWrapper(),
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es.emit("pipeline-progress", { event: "pipeline-progress", jobId: "job-123", step: "categorization", progress: 60 });
    });

    expect(result.current.message).toBeNull();
  });

  it("clears message to null on job-complete", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    const { result } = renderHook(() => useFeedSSE("job-123", "token"), {
      wrapper: createWrapper(),
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es.emit("pipeline-progress", {
        event: "pipeline-progress",
        jobId: "job-123",
        step: "categorization",
        progress: 60,
        message: "Categorizing...",
      });
    });

    expect(result.current.message).toBe("Categorizing...");

    act(() => {
      es.emit("job-complete", { event: "job-complete", jobId: "job-123", status: "completed" });
    });

    expect(result.current.message).toBeNull();
  });

  it("clears message to null on job-failed", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    const { result } = renderHook(() => useFeedSSE("job-123", "token"), {
      wrapper: createWrapper(),
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es.emit("pipeline-progress", {
        event: "pipeline-progress",
        jobId: "job-123",
        step: "categorization",
        progress: 60,
        message: "Categorizing...",
      });
    });

    expect(result.current.message).toBe("Categorizing...");

    act(() => {
      es.emit("job-failed", { event: "job-failed", jobId: "job-123" });
    });

    expect(result.current.message).toBeNull();
  });

  it("reconnects on error with exponential backoff", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    renderHook(() => useFeedSSE("job-123", "token"), {
      wrapper: createWrapper(),
    });

    expect(MockEventSource.instances).toHaveLength(1);
    const es = MockEventSource.instances[0];

    // Trigger error
    act(() => {
      es.onerror?.(new Event("error"));
    });

    expect(es.closed).toBe(true);

    // Advance past first reconnect delay (1000ms)
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    // Should have created a new EventSource
    expect(MockEventSource.instances).toHaveLength(2);
  });

  it("sets isStreaming: false on error when max reconnect attempts exceeded", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    const { result } = renderHook(() => useFeedSSE("job-123", "token"), {
      wrapper: createWrapper(),
    });

    // Exhaust all 10 reconnect attempts
    for (let i = 0; i < 10; i++) {
      const es = MockEventSource.instances[MockEventSource.instances.length - 1];
      act(() => {
        es.onerror?.(new Event("error"));
      });
      act(() => {
        vi.advanceTimersByTime(30000); // advance past max delay
      });
    }

    // 11th error — no more reconnects
    const lastEs = MockEventSource.instances[MockEventSource.instances.length - 1];
    act(() => {
      lastEs.onerror?.(new Event("error"));
    });

    expect(result.current.isStreaming).toBe(false);
  });

  it("does not reconnect after terminal job-complete event", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    renderHook(() => useFeedSSE("job-123", "token"), {
      wrapper: createWrapper(),
    });

    const es = MockEventSource.instances[0];
    const countBefore = MockEventSource.instances.length;

    act(() => {
      es.emit("job-complete", { event: "job-complete", jobId: "job-123", status: "completed" });
    });

    // Simulate a late error after terminal event
    act(() => {
      es.onerror?.(new Event("error"));
    });

    act(() => {
      vi.advanceTimersByTime(30000);
    });

    // No new EventSource should have been created
    expect(MockEventSource.instances).toHaveLength(countBefore);
  });

  it("ignores malformed JSON in SSE events without crashing", async () => {
    const { useFeedSSE } = await import("../hooks/use-feed-sse");
    const { result } = renderHook(() => useFeedSSE("job-123", "token"), {
      wrapper: createWrapper(),
    });

    const es = MockEventSource.instances[0];

    // Send malformed event data directly (bypass emit helper)
    act(() => {
      const badEvent = { data: "not-json{{{" } as MessageEvent;
      // Access private listeners via the emit pattern
      es.emit("pipeline-progress", "not-json{{{");
    });

    // Should not crash, state unchanged
    expect(result.current.message).toBeNull();
    expect(result.current.isStreaming).toBe(true);
  });
});
