import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";
import LocaleSwitcher from "../LocaleSwitcher";

// Track router calls
const mockReplace = vi.fn();

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "uk",
}));

// Mock @/i18n/navigation
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => "/dashboard",
}));

// Mock @/i18n/routing
vi.mock("@/i18n/routing", () => ({
  routing: {
    locales: ["uk", "en"],
    defaultLocale: "uk",
  },
}));

// Mock sonner
const mockToast = vi.fn();
vi.mock("sonner", () => ({
  toast: { success: (...args: unknown[]) => mockToast(...args) },
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("LocaleSwitcher", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockResolvedValue({ ok: true });
  });

  it("8.1 renders current locale with flag and locale code", () => {
    render(<LocaleSwitcher />);

    expect(screen.getByText("UK")).toBeInTheDocument();
    expect(screen.getByText("🇺🇦")).toBeInTheDocument();
  });

  it("8.2 calls PATCH /api/v1/auth/me when accessToken is provided", async () => {
    const user = userEvent.setup();
    render(<LocaleSwitcher accessToken="test-token" />);

    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/me"),
        expect.objectContaining({
          method: "PATCH",
          headers: expect.objectContaining({
            Authorization: "Bearer test-token",
          }),
          body: JSON.stringify({ locale: "en" }),
        })
      );
    });
  });

  it("8.2b does not call backend when no accessToken", async () => {
    const user = userEvent.setup();
    render(<LocaleSwitcher />);

    await user.click(screen.getByRole("button"));

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("8.3 switches route via router.replace with new locale", async () => {
    const user = userEvent.setup();
    render(<LocaleSwitcher />);

    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/dashboard", { locale: "en" });
    });
  });

  it("8.3b shows toast after switching", async () => {
    const user = userEvent.setup();
    render(<LocaleSwitcher />);

    await user.click(screen.getByRole("button"));

    expect(mockToast).toHaveBeenCalledWith("Preference saved", { duration: 2000 });
  });

  it("has accessible aria-label", () => {
    render(<LocaleSwitcher />);

    const button = screen.getByRole("button");
    expect(button).toHaveAttribute("aria-label", expect.stringContaining("Language"));
  });
});
