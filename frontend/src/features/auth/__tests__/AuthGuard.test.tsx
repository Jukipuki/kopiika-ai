import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";
import AuthGuard from "@/lib/auth/auth-guard";

// Mock next-intl
let mockLocale = "en";
vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => mockLocale,
}));

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

describe("AuthGuard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLocale = "en";
  });

  it("7.1 renders loading skeleton while session is loading", () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: "loading",
    });

    render(
      <AuthGuard>
        <div>Protected Content</div>
      </AuthGuard>
    );

    // Should show skeleton, not the content
    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
    // Should render skeleton elements (animate-pulse divs)
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("7.2 redirects to login with callbackUrl when unauthenticated", () => {
    mockLocale = "uk";
    mockPathname.mockReturnValue("/uk/dashboard");
    mockUseSession.mockReturnValue({
      data: null,
      status: "unauthenticated",
    });

    render(
      <AuthGuard>
        <div>Protected Content</div>
      </AuthGuard>
    );

    expect(mockReplace).toHaveBeenCalledWith(
      `/uk/login?callbackUrl=${encodeURIComponent("/uk/dashboard")}`
    );
    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });

  it("7.2b preserves locale in redirect URL (not hardcoded /en/)", () => {
    mockLocale = "de";
    mockPathname.mockReturnValue("/de/settings");
    mockUseSession.mockReturnValue({
      data: null,
      status: "unauthenticated",
    });

    render(
      <AuthGuard>
        <div>Protected Content</div>
      </AuthGuard>
    );

    expect(mockReplace).toHaveBeenCalledWith(
      expect.stringContaining("/de/login")
    );
  });

  it("7.3 renders children when authenticated", () => {
    mockUseSession.mockReturnValue({
      data: { user: { email: "test@example.com" } },
      status: "authenticated",
    });

    render(
      <AuthGuard>
        <div>Protected Content</div>
      </AuthGuard>
    );

    expect(screen.getByText("Protected Content")).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("7.3b treats TokenRefreshFailed as unauthenticated", () => {
    mockPathname.mockReturnValue("/en/dashboard");
    mockUseSession.mockReturnValue({
      data: {
        user: { email: "test@example.com" },
        error: "TokenRefreshFailed",
      },
      status: "authenticated",
    });

    render(
      <AuthGuard>
        <div>Protected Content</div>
      </AuthGuard>
    );

    // Should redirect because of TokenRefreshFailed
    expect(mockReplace).toHaveBeenCalled();
    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });
});
