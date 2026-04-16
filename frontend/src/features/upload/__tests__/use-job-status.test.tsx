import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useJobStatus } from "../hooks/use-job-status";

// Mock next-auth/react
const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

// Mock EventSource
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onopen: ((e: Event) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  readyState = 0; // CONNECTING
  private listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
    // Simulate connection open on next tick
    setTimeout(() => {
      this.readyState = 1; // OPEN
      this.onopen?.(new Event("open"));
    }, 0);
  }

  addEventListener(type: string, listener: (e: MessageEvent) => void) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  removeEventListener(type: string, listener: (e: MessageEvent) => void) {
    if (this.listeners[type]) {
      this.listeners[type] = this.listeners[type].filter((l) => l !== listener);
    }
  }

  close() {
    this.closed = true;
    this.readyState = 2; // CLOSED
  }

  // Test helpers
  simulateEvent(type: string, data: Record<string, unknown>) {
    const event = new MessageEvent(type, { data: JSON.stringify(data) });
    this.listeners[type]?.forEach((l) => l(event));
  }

  simulateError() {
    this.onerror?.(new Event("error"));
  }
}

// Replace global EventSource
const OriginalEventSource = globalThis.EventSource;
beforeEach(() => {
  MockEventSource.instances = [];
  (globalThis as unknown as Record<string, unknown>).EventSource = MockEventSource;
});

afterEach(() => {
  (globalThis as unknown as Record<string, unknown>).EventSource = OriginalEventSource;
});

describe("useJobStatus", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockUseSession.mockReturnValue({
      data: { accessToken: "test-token" },
      status: "authenticated",
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns idle state when jobId is null", () => {
    const { result } = renderHook(() => useJobStatus(null));
    expect(result.current.status).toBe("idle");
    expect(result.current.isConnected).toBe(false);
    expect(MockEventSource.instances).toHaveLength(0);
  });

  it("connects to SSE and parses pipeline-progress events (8.1)", async () => {
    const { result } = renderHook(() => useJobStatus("job-123"));

    // Wait for EventSource to be created
    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    const es = MockEventSource.instances[0];
    expect(es.url).toContain("/api/v1/jobs/job-123/stream");
    expect(es.url).toContain("token=test-token");

    // Simulate progress event
    act(() => {
      es.simulateEvent("pipeline-progress", {
        event: "pipeline-progress",
        jobId: "job-123",
        step: "ingestion",
        progress: 30,
        message: "Parsing...",
      });
    });

    expect(result.current.status).toBe("processing");
    expect(result.current.step).toBe("ingestion");
    expect(result.current.progress).toBe(30);
    expect(result.current.message).toBe("Parsing...");
  });

  it("handles job-complete event", async () => {
    const { result } = renderHook(() => useJobStatus("job-123"));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es.simulateEvent("job-complete", {
        event: "job-complete",
        jobId: "job-123",
        status: "completed",
        totalInsights: 5,
      });
    });

    expect(result.current.status).toBe("completed");
    expect(result.current.progress).toBe(100);
    expect(result.current.result).toMatchObject({ totalInsights: 5 });
    expect(result.current.message).toBeNull();
    expect(es.closed).toBe(true);
  });

  it("captures bankName, transactionCount, dateRange from job-complete (Story 2.8)", async () => {
    const { result } = renderHook(() => useJobStatus("job-123"));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es.simulateEvent("job-complete", {
        event: "job-complete",
        jobId: "job-123",
        status: "completed",
        totalInsights: 12,
        bankName: "Monobank",
        transactionCount: 245,
        dateRange: { start: "2026-02-01", end: "2026-02-28" },
        duplicatesSkipped: 3,
        newTransactions: 245,
      });
    });

    expect(result.current.result).toMatchObject({
      totalInsights: 12,
      bankName: "Monobank",
      transactionCount: 245,
      dateRange: { start: "2026-02-01", end: "2026-02-28" },
      duplicatesSkipped: 3,
      newTransactions: 245,
    });
  });

  it("clears message on terminal events (Story 2.8)", async () => {
    const { result } = renderHook(() => useJobStatus("job-123"));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es.simulateEvent("pipeline-progress", {
        event: "pipeline-progress",
        jobId: "job-123",
        step: "education",
        progress: 80,
        message: "Generated 12 financial insights",
      });
    });

    expect(result.current.message).toBe("Generated 12 financial insights");

    act(() => {
      es.simulateEvent("job-complete", {
        event: "job-complete",
        jobId: "job-123",
        status: "completed",
        totalInsights: 12,
      });
    });

    expect(result.current.message).toBeNull();
  });

  it("handles job-failed event", async () => {
    const { result } = renderHook(() => useJobStatus("job-123"));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es.simulateEvent("job-failed", {
        event: "job-failed",
        jobId: "job-123",
        status: "failed",
        error: { code: "LLM_ERROR", message: "Processing failed" },
      });
    });

    expect(result.current.status).toBe("failed");
    expect(result.current.error).toEqual({
      code: "LLM_ERROR",
      message: "Processing failed",
    });
    expect(es.closed).toBe(true);
  });

  it("auto-reconnects on disconnect with exponential backoff (8.2)", async () => {
    const { result } = renderHook(() => useJobStatus("job-123"));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    const es1 = MockEventSource.instances[0];

    // Simulate error
    act(() => {
      es1.simulateError();
    });

    expect(result.current.isConnected).toBe(false);

    // Advance past first reconnect delay (1000ms)
    await act(async () => {
      vi.advanceTimersByTime(1100);
    });

    // Should have created a new EventSource
    expect(MockEventSource.instances.length).toBeGreaterThanOrEqual(2);
  });

  it("cleans up EventSource on unmount", async () => {
    const { result, unmount } = renderHook(() => useJobStatus("job-123"));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    const es = MockEventSource.instances[0];
    unmount();
    expect(es.closed).toBe(true);
  });

  it("resets state when jobId changes to null", async () => {
    const { result, rerender } = renderHook(
      ({ jobId }) => useJobStatus(jobId),
      { initialProps: { jobId: "job-123" as string | null } },
    );

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    rerender({ jobId: null });

    expect(result.current.status).toBe("idle");
    expect(result.current.isConnected).toBe(false);
  });
});
