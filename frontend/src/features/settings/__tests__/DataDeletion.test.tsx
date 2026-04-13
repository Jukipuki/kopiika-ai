import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createUseTranslations } from "@/test-utils/intl-mock";
import DataDeletion from "../components/DataDeletion";

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

// Mock next-auth/react
const mockSignOut = vi.fn();
const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
  signOut: (...args: unknown[]) => mockSignOut(...args),
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

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("DataDeletion", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSession.mockReturnValue({
      data: { accessToken: "test-token" },
      status: "authenticated",
    });
    mockSignOut.mockResolvedValue(undefined);
  });

  it("renders delete button", () => {
    renderWithQuery(<DataDeletion />);
    expect(screen.getByText("Delete All My Data")).toBeInTheDocument();
  });

  it("opens confirmation dialog on button click", async () => {
    renderWithQuery(<DataDeletion />);
    const user = userEvent.setup();

    await user.click(screen.getByText("Delete All My Data"));

    expect(screen.getByText("Are you absolutely sure?")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
    expect(screen.getByText("Yes, delete everything")).toBeInTheDocument();
  });

  it("closes dialog on cancel", async () => {
    renderWithQuery(<DataDeletion />);
    const user = userEvent.setup();

    await user.click(screen.getByText("Delete All My Data"));
    expect(screen.getByText("Are you absolutely sure?")).toBeInTheDocument();

    await user.click(screen.getByText("Cancel"));

    await waitFor(() => {
      expect(screen.queryByText("Are you absolutely sure?")).not.toBeInTheDocument();
    });
  });

  it("calls API and signs out on successful deletion", async () => {
    mockFetch.mockResolvedValue({ ok: true, status: 204 });

    renderWithQuery(<DataDeletion />);
    const user = userEvent.setup();

    await user.click(screen.getByText("Delete All My Data"));
    await user.click(screen.getByText("Yes, delete everything"));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/users/me"),
        expect.objectContaining({ method: "DELETE" })
      );
    });

    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith(
        "Your data has been deleted. Goodbye!"
      );
      expect(mockSignOut).toHaveBeenCalledWith({
        callbackUrl: "/en/login",
      });
    });
  });

  it("shows error toast and does not sign out on failure", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500 });

    renderWithQuery(<DataDeletion />);
    const user = userEvent.setup();

    await user.click(screen.getByText("Delete All My Data"));
    await user.click(screen.getByText("Yes, delete everything"));

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(
        "Failed to delete your data. Please try again."
      );
    });

    expect(mockSignOut).not.toHaveBeenCalled();
  });
});
