import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import SignupForm from "../components/SignupForm";

const mockOnSuccess = vi.fn();

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("SignupForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all form fields", () => {
    render(<SignupForm onSuccess={mockOnSuccess} />);

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /create account/i })
    ).toBeInTheDocument();
  });

  it("shows email validation error on blur with invalid email", async () => {
    const user = userEvent.setup();
    render(<SignupForm onSuccess={mockOnSuccess} />);

    const emailInput = screen.getByLabelText(/email/i);
    await user.type(emailInput, "not-an-email");
    await user.tab();

    await waitFor(() => {
      expect(
        screen.getByText(/please enter a valid email/i)
      ).toBeInTheDocument();
    });
  });

  it("shows password requirements checklist with real-time feedback", async () => {
    const user = userEvent.setup();
    render(<SignupForm onSuccess={mockOnSuccess} />);

    expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
    expect(screen.getByText(/one uppercase letter/i)).toBeInTheDocument();
    expect(screen.getByText(/one lowercase letter/i)).toBeInTheDocument();
    expect(screen.getByText(/one number/i)).toBeInTheDocument();
    expect(screen.getByText(/one special character/i)).toBeInTheDocument();

    const passwordInput = screen.getByLabelText(/^password$/i);
    await user.type(passwordInput, "Abcdefg1!");

    // After typing a strong password, all requirements should show checkmarks
    await waitFor(() => {
      const items = screen.getAllByText(/✓/);
      expect(items.length).toBe(5);
    });
  });

  it("shows confirm password mismatch error", async () => {
    const user = userEvent.setup();
    render(<SignupForm onSuccess={mockOnSuccess} />);

    await user.type(screen.getByLabelText(/^password$/i), "StrongPass1!");
    await user.type(screen.getByLabelText(/confirm password/i), "Different1!");
    await user.tab();

    await waitFor(() => {
      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
    });
  });

  it("calls API with correct payload on valid submission", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          message: "Verification email sent",
          userId: "test-id",
        }),
    });

    render(<SignupForm onSuccess={mockOnSuccess} />);

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "StrongPass1!");
    await user.type(screen.getByLabelText(/confirm password/i), "StrongPass1!");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/signup"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            email: "test@example.com",
            password: "StrongPass1!",
          }),
        })
      );
      expect(mockOnSuccess).toHaveBeenCalledWith("test@example.com");
    });
  });

  it("displays server error for duplicate email", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () =>
        Promise.resolve({
          error: {
            code: "EMAIL_ALREADY_EXISTS",
            message: "An account with this email already exists",
          },
        }),
    });

    render(<SignupForm onSuccess={mockOnSuccess} />);

    await user.type(screen.getByLabelText(/email/i), "existing@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "StrongPass1!");
    await user.type(screen.getByLabelText(/confirm password/i), "StrongPass1!");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/an account with this email already exists/i)
      ).toBeInTheDocument();
    });
  });
});
