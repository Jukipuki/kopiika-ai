import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ConsentGuard from "@/lib/auth/consent-guard";

// Mock next-intl
vi.mock("next-intl", async () => {
  const { mockNextIntl } = await import("@/test-utils/intl-mock");
  return mockNextIntl;
});

// Mock next-auth/react
const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

// Mock next/navigation
const mockReplace = vi.fn();
const mockPathname = vi.fn(() => "/en/dashboard");
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => mockPathname(),
}));

const mockFetch = vi.fn();
global.fetch = mockFetch as unknown as typeof fetch;

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe("ConsentGuard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPathname.mockReturnValue("/en/dashboard");
    mockUseSession.mockReturnValue({
      data: { accessToken: "test-token" },
      status: "authenticated",
    });
  });

  it("renders children when user has current consent", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          hasCurrentConsent: true,
          version: "2026-04-11-v1",
          grantedAt: "2026-04-11T00:00:00Z",
          locale: "en",
        }),
    });

    renderWithClient(
      <ConsentGuard>
        <div>Dashboard Content</div>
      </ConsentGuard>
    );

    await waitFor(() => {
      expect(screen.getByText("Dashboard Content")).toBeInTheDocument();
    });
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("redirects to /onboarding/privacy when hasCurrentConsent is false", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          hasCurrentConsent: false,
          version: "2026-04-11-v1",
          grantedAt: null,
          locale: null,
        }),
    });

    renderWithClient(
      <ConsentGuard>
        <div>Dashboard Content</div>
      </ConsentGuard>
    );

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/en/onboarding/privacy");
    });
    expect(screen.queryByText("Dashboard Content")).not.toBeInTheDocument();
  });

  it("short-circuits on onboarding routes and renders children without fetching", async () => {
    mockPathname.mockReturnValue("/en/onboarding/privacy");

    renderWithClient(
      <ConsentGuard>
        <div>Onboarding Content</div>
      </ConsentGuard>
    );

    expect(screen.getByText("Onboarding Content")).toBeInTheDocument();
    expect(mockFetch).not.toHaveBeenCalled();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("shows loading skeleton while consent query is pending", () => {
    // Never resolve — keeps query in loading state
    mockFetch.mockReturnValue(new Promise(() => {}));

    renderWithClient(
      <ConsentGuard>
        <div>Dashboard Content</div>
      </ConsentGuard>
    );

    expect(screen.queryByText("Dashboard Content")).not.toBeInTheDocument();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("redirects to /onboarding/privacy when consent fetch fails (fail-closed)", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    renderWithClient(
      <ConsentGuard>
        <div>Dashboard Content</div>
      </ConsentGuard>
    );

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/en/onboarding/privacy");
    });
    expect(screen.queryByText("Dashboard Content")).not.toBeInTheDocument();
  });
});
