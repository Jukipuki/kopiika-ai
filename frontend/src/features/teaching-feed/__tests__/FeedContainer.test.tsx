import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { FeedContainer } from "../components/FeedContainer";
import type { InsightCard } from "../types";

// Mock next-auth/react
const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock @/i18n/navigation
vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...props }: { href: string; children: React.ReactNode }) =>
    React.createElement("a", { href, ...props }, children),
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
    mockUseSession.mockReturnValue({ data: { accessToken: "test-token" } });
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

  it("renders insight cards on success", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ items: mockItems, total: 2, nextCursor: null, hasMore: false }),
    });
    render(<FeedContainer />, { wrapper: createWrapper() });
    await waitFor(() =>
      expect(screen.getByText("You spent 30% more on food")).toBeInTheDocument(),
    );
    expect(screen.getByText("Utility bills increased")).toBeInTheDocument();
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
  });
});
