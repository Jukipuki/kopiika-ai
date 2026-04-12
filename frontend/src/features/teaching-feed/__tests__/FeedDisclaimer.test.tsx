import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { FeedDisclaimer } from "../components/FeedDisclaimer";

vi.mock("next-intl", async () => {
  const { mockNextIntl } = await import("@/test-utils/intl-mock");
  return mockNextIntl;
});

describe("FeedDisclaimer", () => {
  it("renders the short disclaimer text", () => {
    render(<FeedDisclaimer />);
    expect(
      screen.getByText(/educational insights only/i),
    ).toBeInTheDocument();
  });

  it("does not show the full text by default", () => {
    render(<FeedDisclaimer />);
    expect(
      screen.queryByText(/consult a qualified advisor/i),
    ).not.toBeInTheDocument();
  });

  it("expands to show full text when info button is clicked", async () => {
    const user = userEvent.setup();
    render(<FeedDisclaimer />);

    const toggle = screen.getByRole("button", {
      name: /toggle disclaimer details/i,
    });
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    await user.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByText(/consult a qualified advisor/i),
    ).toBeInTheDocument();
  });

  it("collapses full text on second click", async () => {
    const user = userEvent.setup();
    render(<FeedDisclaimer />);

    const toggle = screen.getByRole("button", {
      name: /toggle disclaimer details/i,
    });
    await user.click(toggle);
    await user.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.queryByText(/consult a qualified advisor/i),
    ).not.toBeInTheDocument();
  });
});
