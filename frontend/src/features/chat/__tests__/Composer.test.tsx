import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";
import { Composer } from "../components/Composer";

vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

describe("Composer", () => {
  it("Enter sends, Shift+Enter inserts newline", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<Composer onSend={onSend} disabled={false} />);
    const ta = screen.getByPlaceholderText(/finances/i);
    await user.type(ta, "hello");
    await user.keyboard("{Enter}");
    expect(onSend).toHaveBeenCalledWith("hello");

    onSend.mockClear();
    await user.type(ta, "line one");
    await user.keyboard("{Shift>}{Enter}{/Shift}line two");
    await user.keyboard("{Enter}");
    expect(onSend).toHaveBeenCalledWith("line one\nline two");
  });

  it("char counter appears at 70% of 4096", async () => {
    const user = userEvent.setup();
    render(<Composer onSend={vi.fn()} disabled={false} />);
    const ta = screen.getByPlaceholderText(/finances/i);
    // Below threshold — no counter.
    await user.type(ta, "x");
    expect(screen.queryByText(/\/4096/)).toBeNull();
    // At/above threshold (70% of 4096 ≈ 2867).
    const long = "y".repeat(2870);
    // user.type is too slow for 2870 chars; use fireEvent via paste.
    await user.clear(ta);
    await user.click(ta);
    await user.paste(long);
    expect(screen.getByText(/\/4096/)).toBeInTheDocument();
  });

  it("Send disabled while stream in-flight, Enter intercepted with hint", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<Composer onSend={onSend} disabled={true} />);
    const ta = screen.getByPlaceholderText(/finances/i);
    await user.type(ta, "ping");
    await user.keyboard("{Enter}");
    expect(onSend).not.toHaveBeenCalled();
    expect(screen.getByText(/wait for the response/i)).toBeInTheDocument();
  });

  it("cooldown active disables Send and announces hint", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<Composer onSend={onSend} disabled={false} cooldownActive={true} />);
    await user.type(screen.getByPlaceholderText(/finances/i), "ping");
    await user.keyboard("{Enter}");
    expect(onSend).not.toHaveBeenCalled();
    expect(screen.getByText(/cooldown/i)).toBeInTheDocument();
  });
});
