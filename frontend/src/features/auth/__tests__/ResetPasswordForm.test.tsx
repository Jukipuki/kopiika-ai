import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";
import ResetPasswordForm from "../components/ResetPasswordForm";

vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

const mockPush = vi.fn();
vi.mock("@/i18n/navigation", async () => {
  const React = await import("react");
  return {
    Link: ({
      href,
      children,
      ...props
    }: {
      href: string | { pathname: string; query?: Record<string, string> };
      children: React.ReactNode;
    } & Record<string, unknown>) => {
      const resolvedHref =
        typeof href === "string"
          ? href
          : `${href.pathname}${
              href.query
                ? `?${new URLSearchParams(href.query).toString()}`
                : ""
            }`;
      return React.createElement(
        "a",
        { href: resolvedHref, ...props },
        children
      );
    },
    useRouter: () => ({ push: mockPush, replace: vi.fn() }),
  };
});

let mockSearchParams = new URLSearchParams({ email: "user@example.com" });
vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
}));

const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("ResetPasswordForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders reset code, new password, and confirm password fields", () => {
    render(<ResetPasswordForm />);

    expect(screen.getByLabelText(/reset code/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^new password$/i)).toBeInTheDocument();
    expect(
      screen.getByLabelText(/confirm new password/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /update password/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /request a new code/i })
    ).toBeInTheDocument();
    // Pre-fills email from search params
    expect(screen.getByText("user@example.com")).toBeInTheDocument();
  });

  it("submits POST to /api/v1/auth/reset-password with correct payload", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ message: "Password updated successfully" }),
    });

    render(<ResetPasswordForm />);

    await user.type(screen.getByLabelText(/reset code/i), "123456");
    await user.type(
      screen.getByLabelText(/^new password$/i),
      "BrandNewPass1!"
    );
    await user.type(
      screen.getByLabelText(/confirm new password/i),
      "BrandNewPass1!"
    );
    await user.click(
      screen.getByRole("button", { name: /update password/i })
    );

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/reset-password"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            email: "user@example.com",
            code: "123456",
            newPassword: "BrandNewPass1!",
          }),
        })
      );
    });
  });

  it("redirects to /login?reset=success on successful password reset", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ message: "Password updated successfully" }),
    });

    render(<ResetPasswordForm />);

    await user.type(screen.getByLabelText(/reset code/i), "123456");
    await user.type(
      screen.getByLabelText(/^new password$/i),
      "BrandNewPass1!"
    );
    await user.type(
      screen.getByLabelText(/confirm new password/i),
      "BrandNewPass1!"
    );
    await user.click(
      screen.getByRole("button", { name: /update password/i })
    );

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/login?reset=success");
    });
  });

  it("shows invalidCode error for RESET_CODE_INVALID", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () =>
        Promise.resolve({
          error: {
            code: "RESET_CODE_INVALID",
            message: "Reset code is invalid",
          },
        }),
    });

    render(<ResetPasswordForm />);

    await user.type(screen.getByLabelText(/reset code/i), "000000");
    await user.type(
      screen.getByLabelText(/^new password$/i),
      "BrandNewPass1!"
    );
    await user.type(
      screen.getByLabelText(/confirm new password/i),
      "BrandNewPass1!"
    );
    await user.click(
      screen.getByRole("button", { name: /update password/i })
    );

    await waitFor(() => {
      expect(
        screen.getByText(/reset code is invalid or has expired/i)
      ).toBeInTheDocument();
    });
  });

  it("shows invalidCode error for RESET_CODE_EXPIRED", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () =>
        Promise.resolve({
          error: {
            code: "RESET_CODE_EXPIRED",
            message: "Reset code has expired",
          },
        }),
    });

    render(<ResetPasswordForm />);

    await user.type(screen.getByLabelText(/reset code/i), "123456");
    await user.type(
      screen.getByLabelText(/^new password$/i),
      "BrandNewPass1!"
    );
    await user.type(
      screen.getByLabelText(/confirm new password/i),
      "BrandNewPass1!"
    );
    await user.click(
      screen.getByRole("button", { name: /update password/i })
    );

    await waitFor(() => {
      expect(
        screen.getByText(/reset code is invalid or has expired/i)
      ).toBeInTheDocument();
    });
  });

  it("shows client-side error for password mismatch", async () => {
    const user = userEvent.setup();
    render(<ResetPasswordForm />);

    await user.type(screen.getByLabelText(/reset code/i), "123456");
    await user.type(
      screen.getByLabelText(/^new password$/i),
      "BrandNewPass1!"
    );
    await user.type(
      screen.getByLabelText(/confirm new password/i),
      "DifferentPass1!"
    );
    await user.tab();

    await waitFor(() => {
      expect(
        screen.getByText(/passwords do not match/i)
      ).toBeInTheDocument();
    });
  });

  it("disables button during submission", async () => {
    const user = userEvent.setup();
    type FetchResolver = (value: unknown) => void;
    let resolveFetch: FetchResolver | undefined;
    mockFetch.mockImplementationOnce(
      () =>
        new Promise<unknown>((r) => {
          resolveFetch = r;
        })
    );

    render(<ResetPasswordForm />);

    await user.type(screen.getByLabelText(/reset code/i), "123456");
    await user.type(
      screen.getByLabelText(/^new password$/i),
      "BrandNewPass1!"
    );
    await user.type(
      screen.getByLabelText(/confirm new password/i),
      "BrandNewPass1!"
    );
    await user.click(
      screen.getByRole("button", { name: /update password/i })
    );

    await waitFor(() => {
      const button = screen.getByRole("button", { name: /updating/i });
      expect(button).toBeDisabled();
    });

    resolveFetch?.({
      ok: true,
      json: () => Promise.resolve({ message: "ok" }),
    });
  });

  it("renders back link to /forgot-password", () => {
    render(<ResetPasswordForm />);

    const backLink = screen.getByRole("link", { name: /request a new code/i });
    expect(backLink).toHaveAttribute("href", "/forgot-password");
  });

  it("shows error guard and back link when email query param is missing", () => {
    const original = mockSearchParams;
    mockSearchParams = new URLSearchParams();

    try {
      render(<ResetPasswordForm />);

      expect(
        screen.getByText(/reset code is invalid or has expired/i)
      ).toBeInTheDocument();
      expect(
        screen.queryByLabelText(/reset code/i)
      ).not.toBeInTheDocument();
      const backLink = screen.getByRole("link", {
        name: /request a new code/i,
      });
      expect(backLink).toHaveAttribute("href", "/forgot-password");
    } finally {
      mockSearchParams = original;
    }
  });
});
