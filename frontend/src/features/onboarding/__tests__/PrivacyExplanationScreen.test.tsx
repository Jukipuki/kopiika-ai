import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import PrivacyExplanationScreen from "../components/PrivacyExplanationScreen";
import { CURRENT_CONSENT_VERSION } from "@/features/onboarding/consent-version";

// Mock next-intl
vi.mock("next-intl", async () => {
  const { mockNextIntl } = await import("@/test-utils/intl-mock");
  return mockNextIntl;
});

// Mock next-auth/react
const mockUseSession = vi.fn();
const mockSignOut = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
  signOut: (...args: unknown[]) => mockSignOut(...args),
}));

// Mock next/navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
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

describe("PrivacyExplanationScreen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSession.mockReturnValue({
      data: { accessToken: "test-token" },
      status: "authenticated",
    });
  });

  it("renders the four privacy topics, the disclaimer section, and a disabled Continue button", () => {
    renderWithClient(<PrivacyExplanationScreen />);

    expect(screen.getByText(/what we collect/i)).toBeInTheDocument();
    expect(screen.getByText(/how ai processes it/i)).toBeInTheDocument();
    expect(screen.getByText(/where it's stored/i)).toBeInTheDocument();
    expect(screen.getByText(/who can see it/i)).toBeInTheDocument();
    expect(screen.getByText(/financial advice disclaimer/i)).toBeInTheDocument();
    expect(screen.getByText(/this is not professional financial advice/i)).toBeInTheDocument();

    const continueBtn = screen.getByRole("button", { name: /continue/i });
    expect(continueBtn).toBeDisabled();
  });

  it("enables the Continue button only after the consent checkbox is checked", async () => {
    const user = userEvent.setup();
    renderWithClient(<PrivacyExplanationScreen />);

    const checkbox = screen.getByRole("checkbox");
    const continueBtn = screen.getByRole("button", { name: /continue/i });

    expect(continueBtn).toBeDisabled();
    await user.click(checkbox);
    expect(continueBtn).toBeEnabled();
  });

  it("POSTs consent payload with version + locale and redirects to /upload on success", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          id: "consent-id",
          version: CURRENT_CONSENT_VERSION,
          grantedAt: "2026-04-11T00:00:00Z",
          locale: "en",
        }),
    });

    renderWithClient(<PrivacyExplanationScreen />);
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/users/me/consent"),
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            Authorization: "Bearer test-token",
            "Content-Type": "application/json",
          }),
          body: JSON.stringify({
            version: CURRENT_CONSENT_VERSION,
            locale: "en",
          }),
        })
      );
      expect(mockPush).toHaveBeenCalledWith("/en/upload");
    });
  });

  it("displays a server error message on non-ok response and does not redirect", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () =>
        Promise.resolve({
          error: {
            code: "CONSENT_VERSION_MISMATCH",
            message: "Stale consent version",
          },
        }),
    });

    renderWithClient(<PrivacyExplanationScreen />);
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /stale consent version/i
      );
    });
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("does not submit when checkbox is unchecked", async () => {
    const user = userEvent.setup();
    renderWithClient(<PrivacyExplanationScreen />);

    // Force-click the disabled button — it still should not fire fetch
    const btn = screen.getByRole("button", { name: /continue/i });
    await user.click(btn).catch(() => {});
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("calls signOut from the Log out link", async () => {
    const user = userEvent.setup();
    renderWithClient(<PrivacyExplanationScreen />);

    await user.click(screen.getByRole("button", { name: /log out/i }));
    expect(mockSignOut).toHaveBeenCalledWith(
      expect.objectContaining({ callbackUrl: "/en/login" })
    );
  });
});
