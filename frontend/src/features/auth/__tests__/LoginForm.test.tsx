import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";
import LoginForm from "../components/LoginForm";

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

// Mock @/i18n/navigation (Link used for forgot-password)
vi.mock("@/i18n/navigation", async () => {
  const React = await import("react");
  return {
    Link: ({ href, children, ...props }: Record<string, unknown>) => {
      return React.createElement("a", { href, ...props }, children);
    },
  };
});

// Mock next-auth/react
const mockSignIn = vi.fn();
vi.mock("next-auth/react", () => ({
  signIn: (...args: unknown[]) => mockSignIn(...args),
}));

// Mock next/navigation
const mockPush = vi.fn();
const mockSearchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => mockSearchParams,
}));

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("LoginForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("10.1 renders email and password fields", () => {
    render(<LoginForm />);

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sign in/i })
    ).toBeInTheDocument();
  });

  it("10.2 email validation on blur shows error for invalid email", async () => {
    const user = userEvent.setup();
    render(<LoginForm />);

    const emailInput = screen.getByLabelText(/email/i);
    await user.type(emailInput, "not-an-email");
    await user.tab();

    await waitFor(() => {
      expect(
        screen.getByText(/please enter a valid email/i)
      ).toBeInTheDocument();
    });
  });

  it("10.3 form submission calls login API with correct payload", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          accessToken: "test-access-token",
          refreshToken: "test-refresh-token",
          expiresIn: 900,
          user: { id: "user-1", email: "test@example.com", locale: "uk" },
        }),
    });
    mockSignIn.mockResolvedValueOnce({ error: null });

    render(<LoginForm />);

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/password/i), "StrongPass1!");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/login"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            email: "test@example.com",
            password: "StrongPass1!",
          }),
        })
      );
    });
  });

  it("10.4 invalid credentials error displays user-friendly message", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () =>
        Promise.resolve({
          error: {
            code: "INVALID_CREDENTIALS",
            message: "Invalid email or password",
          },
        }),
      headers: new Headers(),
    });

    render(<LoginForm />);

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/password/i), "WrongPass!");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/invalid email or password/i)
      ).toBeInTheDocument();
    });
  });

  it("10.5 rate limit error displays countdown timer", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () =>
        Promise.resolve({
          error: {
            code: "RATE_LIMITED",
            message: "Too many login attempts",
            details: { retryAfter: 120 },
          },
        }),
      headers: new Headers({ "Retry-After": "120" }),
    });

    render(<LoginForm />);

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/password/i), "WrongPass!");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/too many login attempts/i)
      ).toBeInTheDocument();
    });

    // Submit button should be disabled
    const button = screen.getByRole("button");
    expect(button).toBeDisabled();
  });

  it("10.6 successful login redirects to dashboard", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          accessToken: "test-access-token",
          refreshToken: "test-refresh-token",
          expiresIn: 900,
          user: { id: "user-1", email: "test@example.com", locale: "uk" },
        }),
    });
    mockSignIn.mockResolvedValueOnce({ error: null });

    render(<LoginForm />);

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/password/i), "StrongPass1!");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(mockSignIn).toHaveBeenCalledWith(
        "credentials",
        expect.objectContaining({
          redirect: false,
          accessToken: "test-access-token",
          refreshToken: "test-refresh-token",
        })
      );
      expect(mockPush).toHaveBeenCalledWith("/en/dashboard");
    });
  });
});
