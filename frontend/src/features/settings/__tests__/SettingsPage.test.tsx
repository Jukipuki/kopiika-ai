import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";
import SettingsPage from "../components/SettingsPage";

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

// Mock @/i18n/navigation
const mockReplace = vi.fn();
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => "/settings",
  Link: ({ children, ...props }: { children: React.ReactNode; href: string }) => (
    <a {...props}>{children}</a>
  ),
}));

// Mock @/i18n/routing
vi.mock("@/i18n/routing", () => ({
  routing: {
    locales: ["uk", "en"],
    defaultLocale: "uk",
  },
}));

// Mock sonner
const mockToastSuccess = vi.fn();
const mockToastError = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => mockToastSuccess(...args),
    error: (...args: unknown[]) => mockToastError(...args),
  },
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

const mockProfile = {
  id: "user-123",
  email: "test@example.com",
  locale: "en",
  isVerified: true,
  createdAt: "2025-01-15T10:30:00Z",
};

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLocale = "en";
    mockUseSession.mockReturnValue({
      data: { accessToken: "test-token" },
      status: "authenticated",
    });
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockProfile),
    });
  });

  it("8.1 renders loading skeleton while profile is being fetched", () => {
    // Make fetch never resolve to keep loading state
    mockFetch.mockReturnValue(new Promise(() => {}));

    render(<SettingsPage />);

    // Should render skeleton elements
    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
    // Should NOT render settings content
    expect(screen.queryByText("Account Settings")).not.toBeInTheDocument();
  });

  it("8.2 displays email, locale, and creation date after successful fetch", async () => {
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("test@example.com")).toBeInTheDocument();
    });

    // Page title
    expect(screen.getByText("Account Settings")).toBeInTheDocument();
    // Email displayed
    expect(screen.getByText("test@example.com")).toBeInTheDocument();
    // Verification badge
    expect(screen.getByText("Verified")).toBeInTheDocument();
    // Creation date is formatted
    expect(screen.getByText(/January/)).toBeInTheDocument();
  });

  it("8.3 renders email, formatted date, and verification badge in AccountInfoSection", async () => {
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("test@example.com")).toBeInTheDocument();
    });

    // Account info section heading
    expect(screen.getByText("Account Information")).toBeInTheDocument();
    // Email label
    expect(screen.getByText("Email")).toBeInTheDocument();
    // Member since label
    expect(screen.getByText("Member since")).toBeInTheDocument();
    // Verification badge with aria-label
    const badge = screen.getByLabelText("Verified");
    expect(badge).toBeInTheDocument();
  });

  it("8.3b renders 'Not verified' badge when email is not verified", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ...mockProfile, isVerified: false }),
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("Not verified")).toBeInTheDocument();
    });

    const badge = screen.getByLabelText("Not verified");
    expect(badge).toBeInTheDocument();
  });

  it("8.4 renders language preference section", async () => {
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("test@example.com")).toBeInTheDocument();
    });

    // Language section heading
    expect(screen.getByText("Language")).toBeInTheDocument();
    // Description
    expect(
      screen.getByText("Choose your preferred language for the interface")
    ).toBeInTheDocument();
  });

  it("8.5 calls PATCH /api/v1/auth/me on language change", async () => {
    const user = userEvent.setup();

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("test@example.com")).toBeInTheDocument();
    });

    // Clear the GET /me fetch call
    mockFetch.mockClear();
    mockFetch.mockResolvedValue({ ok: true });

    // Click the language select trigger (combobox role)
    const trigger = screen.getByRole("combobox", { name: "Language" });
    await user.click(trigger);

    // Wait for dropdown to open and click "Українська" option
    const ukrainianOption = await screen.findByRole("option", { name: "Українська" });
    await user.click(ukrainianOption);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/me"),
        expect.objectContaining({
          method: "PATCH",
          headers: expect.objectContaining({
            Authorization: "Bearer test-token",
          }),
          body: JSON.stringify({ locale: "uk" }),
        })
      );
    });
  });

  it("8.6 shows toast on successful language change", async () => {
    const user = userEvent.setup();

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("test@example.com")).toBeInTheDocument();
    });

    mockFetch.mockClear();
    mockFetch.mockResolvedValue({ ok: true });

    const trigger = screen.getByRole("combobox", { name: "Language" });
    await user.click(trigger);

    const ukrainianOption = await screen.findByRole("option", { name: "Українська" });
    await user.click(ukrainianOption);

    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith("Preference saved", {
        duration: 2000,
      });
    });
  });

  it("8.7 shows error state when GET /api/v1/auth/me fails", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Unable to connect to the server. Please try again.")
      ).toBeInTheDocument();
    });

    // Retry button should be present
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("8.7b retries fetch when retry button is clicked", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("Retry")).toBeInTheDocument();
    });

    // Clear and set up successful response
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockProfile),
    });

    const user = userEvent.setup();
    await user.click(screen.getByText("Retry"));

    await waitFor(() => {
      expect(screen.getByText("test@example.com")).toBeInTheDocument();
    });
  });

  it("8.6b shows error toast when PATCH /api/v1/auth/me fails", async () => {
    const user = userEvent.setup();

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("test@example.com")).toBeInTheDocument();
    });

    mockFetch.mockClear();
    mockFetch.mockResolvedValue({ ok: false, status: 500 });

    const trigger = screen.getByRole("combobox", { name: "Language" });
    await user.click(trigger);

    const ukrainianOption = await screen.findByRole("option", { name: "Українська" });
    await user.click(ukrainianOption);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("Failed to save preference", {
        duration: 4000,
      });
    });
  });

  it("8.8 renders correct translated strings", async () => {
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("test@example.com")).toBeInTheDocument();
    });

    // Verify English translations render correctly
    expect(screen.getByText("Account Settings")).toBeInTheDocument();
    expect(screen.getByText("Account Information")).toBeInTheDocument();
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByText("Member since")).toBeInTheDocument();
    expect(screen.getByText("Language")).toBeInTheDocument();
    expect(
      screen.getByText("Choose your preferred language for the interface")
    ).toBeInTheDocument();
  });
});
