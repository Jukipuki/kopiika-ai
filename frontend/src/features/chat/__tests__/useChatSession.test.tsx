import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: { accessToken: "tok" }, status: "authenticated" }),
}));

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // eslint-disable-next-line react/display-name
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useChatSession (Story 10.10 refactor)", () => {
  it("sessions come from the server query (no localSessions merge)", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        sessions: [
          { sessionId: "srv-1", createdAt: "2026-04-26T10:00:00Z" },
        ],
      }),
    });
    const { useChatSession } = await import("../hooks/useChatSession");
    const { result } = renderHook(() => useChatSession(), { wrapper: wrap() });
    await waitFor(() => expect(result.current.sessions.length).toBe(1));
    expect(result.current.sessions[0].sessionId).toBe("srv-1");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/chat/sessions"),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer tok" }),
      }),
    );
  });

  it("bulkDeleteAll issues DELETE /chat/sessions and clears active session", async () => {
    fetchMock
      // initial GET
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          sessions: [{ sessionId: "s1", createdAt: "2026-04-26T10:00:00Z" }],
        }),
      })
      // bulk DELETE
      .mockResolvedValueOnce({ ok: true, status: 204 })
      // refetch after invalidate
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ sessions: [] }),
      });

    const { useChatSession } = await import("../hooks/useChatSession");
    const { result } = renderHook(() => useChatSession(), { wrapper: wrap() });
    await waitFor(() => expect(result.current.sessions.length).toBe(1));

    act(() => result.current.selectSession("s1"));
    expect(result.current.activeSessionId).toBe("s1");

    await act(async () => {
      await result.current.bulkDeleteAll();
    });

    const deleteCall = fetchMock.mock.calls.find(
      (c) =>
        typeof c[0] === "string" &&
        c[0].endsWith("/api/v1/chat/sessions") &&
        c[1]?.method === "DELETE",
    );
    expect(deleteCall).toBeTruthy();
    expect(result.current.activeSessionId).toBeNull();
  });
});
