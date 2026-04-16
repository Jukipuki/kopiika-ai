import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";
import ForgotPasswordForm from "../components/ForgotPasswordForm";

vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

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
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  };
});

const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("ForgotPasswordForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders email field and submit button", () => {
    render(<ForgotPasswordForm />);

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /send reset code/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /back to login/i })
    ).toBeInTheDocument();
  });

  it("validates email format on blur", async () => {
    const user = userEvent.setup();
    render(<ForgotPasswordForm />);

    const emailInput = screen.getByLabelText(/email/i);
    await user.type(emailInput, "not-an-email");
    await user.tab();

    await waitFor(() => {
      expect(
        screen.getByText(/please enter a valid email/i)
      ).toBeInTheDocument();
    });
  });

  it("submits POST to /api/v1/auth/forgot-password with email payload", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          message: "If an account exists, a reset code has been sent",
        }),
    });

    render(<ForgotPasswordForm />);

    await user.type(
      screen.getByLabelText(/email/i),
      "someone@example.com"
    );
    await user.click(
      screen.getByRole("button", { name: /send reset code/i })
    );

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/forgot-password"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ email: "someone@example.com" }),
        })
      );
    });
  });

  it("shows confirmation panel after successful submission", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          message: "If an account exists, a reset code has been sent",
        }),
    });

    render(<ForgotPasswordForm />);

    await user.type(
      screen.getByLabelText(/email/i),
      "someone@example.com"
    );
    await user.click(
      screen.getByRole("button", { name: /send reset code/i })
    );

    await waitFor(() => {
      expect(screen.getByText(/check your email/i)).toBeInTheDocument();
      expect(screen.getByText("someone@example.com")).toBeInTheDocument();
    });

    const enterCodeLink = screen.getByRole("link", {
      name: /enter reset code/i,
    });
    expect(enterCodeLink).toBeInTheDocument();
    expect(enterCodeLink.getAttribute("href")).toContain(
      "/forgot-password/confirm"
    );
    expect(enterCodeLink.getAttribute("href")).toContain(
      "email=someone%40example.com"
    );
  });

  it("shows error alert for USER_NOT_CONFIRMED response", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () =>
        Promise.resolve({
          error: {
            code: "USER_NOT_CONFIRMED",
            message: "Please verify your email",
          },
        }),
    });

    render(<ForgotPasswordForm />);

    await user.type(
      screen.getByLabelText(/email/i),
      "unverified@example.com"
    );
    await user.click(
      screen.getByRole("button", { name: /send reset code/i })
    );

    await waitFor(() => {
      expect(
        screen.getByText(/verify your email before logging in/i)
      ).toBeInTheDocument();
    });
  });

  it("shows generic server error on network failure", async () => {
    const user = userEvent.setup();
    mockFetch.mockRejectedValueOnce(new Error("network down"));

    render(<ForgotPasswordForm />);

    await user.type(
      screen.getByLabelText(/email/i),
      "someone@example.com"
    );
    await user.click(
      screen.getByRole("button", { name: /send reset code/i })
    );

    await waitFor(() => {
      expect(
        screen.getByText(/unable to connect to the server/i)
      ).toBeInTheDocument();
    });
  });

  it("disables button and shows loading text during submission", async () => {
    const user = userEvent.setup();
    type FetchResolver = (value: unknown) => void;
    let resolveFetch: FetchResolver | undefined;
    mockFetch.mockImplementationOnce(
      () =>
        new Promise<unknown>((r) => {
          resolveFetch = r;
        })
    );

    render(<ForgotPasswordForm />);

    await user.type(
      screen.getByLabelText(/email/i),
      "someone@example.com"
    );
    await user.click(
      screen.getByRole("button", { name: /send reset code/i })
    );

    await waitFor(() => {
      const button = screen.getByRole("button", { name: /sending/i });
      expect(button).toBeDisabled();
    });

    resolveFetch?.({
      ok: true,
      json: () => Promise.resolve({ message: "ok" }),
    });
  });
});
