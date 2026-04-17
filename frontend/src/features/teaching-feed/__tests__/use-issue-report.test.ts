import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";

const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

import { useIssueReport } from "../hooks/use-issue-report";

const mockFetch = vi.fn();

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const Wrapper = ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
  Wrapper.displayName = "TestQueryClientWrapper";
  return Wrapper;
}

describe("useIssueReport", () => {
  beforeEach(() => {
    mockUseSession.mockReturnValue({
      data: { accessToken: "test-token" },
    });
    global.fetch = mockFetch as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    mockFetch.mockReset();
  });

  it("posts to /report endpoint with camelCase body", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({
        id: "uuid-1",
        cardId: "card-1",
        issueCategory: "bug",
      }),
    });

    const { result } = renderHook(() => useIssueReport("card-1"), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.submitReport({ issueCategory: "bug", freeText: "broken" });
    });

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/feedback/cards/card-1/report"),
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            Authorization: "Bearer test-token",
            "Content-Type": "application/json",
          }),
          body: JSON.stringify({
            issueCategory: "bug",
            freeText: "broken",
          }),
        }),
      );
    });
  });

  it("sends null freeText when omitted", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ id: "u", cardId: "card-2", issueCategory: "other" }),
    });

    const { result } = renderHook(() => useIssueReport("card-2"), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.submitReport({ issueCategory: "other" });
    });

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/feedback/cards/card-2/report"),
        expect.objectContaining({
          body: JSON.stringify({
            issueCategory: "other",
            freeText: null,
          }),
        }),
      );
    });
  });

  it("sets confirmationShown on 201 success", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({
        id: "uuid-3",
        cardId: "card-3",
        issueCategory: "confusing",
      }),
    });

    const { result } = renderHook(() => useIssueReport("card-3"), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.submitReport({ issueCategory: "confusing" });
    });

    await waitFor(() => {
      expect(result.current.confirmationShown).toBe(true);
    });
    expect(result.current.isAlreadyReported).toBe(false);
  });

  it("sets isAlreadyReported on 409 without throwing", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({ detail: "already_reported" }),
    });

    const { result } = renderHook(() => useIssueReport("card-4"), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.submitReport({ issueCategory: "bug" });
    });

    await waitFor(() => {
      expect(result.current.isAlreadyReported).toBe(true);
    });
    expect(result.current.confirmationShown).toBe(false);
  });
});
