import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";
import { RefusalBubble } from "../components/RefusalBubble";
import type { ChatTurnState } from "../hooks/useChatStream";
import type { RefusalReason } from "../lib/chat-types";

vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

function makeTurn(reason: RefusalReason, retryAfterSeconds: number | null = null): ChatTurnState {
  return {
    id: "t1",
    role: "assistant",
    text: "",
    createdAt: "2026-04-26T10:30:00Z",
    streaming: false,
    refusal: { reason, correlationId: "abcd1234-ef56-7890-1234-567890abcdef", retryAfterSeconds },
  };
}

describe("RefusalBubble", () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  beforeEach(() => {
    // navigator.clipboard may or may not exist in jsdom; defineProperty
    // works for both new instance and prototype-getter cases.
    Object.defineProperty(window.navigator, "clipboard", {
      configurable: true,
      writable: true,
      value: { writeText },
    });
    writeText.mockClear();
  });

  const reasons: RefusalReason[] = [
    "guardrail_blocked",
    "ungrounded",
    "rate_limited",
    "prompt_leak_detected",
    "tool_blocked",
    "transient_error",
  ];

  for (const reason of reasons) {
    it(`renders reason-specific copy for "${reason}"`, () => {
      const turn = makeTurn(reason);
      render(<RefusalBubble turn={turn} />);
      // Reference row + correlationId short form is universal.
      expect(screen.getByText(/Reference: abcd1234/)).toBeInTheDocument();
      // Forbidden internal terms must NOT leak into rendered copy.
      const html = document.body.innerHTML.toLowerCase();
      for (const forbidden of ["guardrail", "grounding", "canary", "jailbreak", "prompt injection"]) {
        expect(html).not.toContain(forbidden);
      }
    });
  }

  it("clipboard copy flips label to Copied (and full UUID is exposed for SR)", async () => {
    const user = userEvent.setup();
    render(<RefusalBubble turn={makeTurn("guardrail_blocked")} />);
    // Full UUID rendered in sr-only span for screen readers (AC #7).
    expect(document.body.innerHTML).toContain("abcd1234-ef56-7890-1234-567890abcdef");
    const btn = screen.getByRole("button", { name: /copy/i });
    await user.click(btn);
    expect(await screen.findByText(/copied/i)).toBeInTheDocument();
  });

  it("rate_limited renders mm:ss countdown driven by retryAfterSeconds", () => {
    vi.useFakeTimers({ shouldAdvanceTime: false });
    render(<RefusalBubble turn={makeTurn("rate_limited", 120)} />);
    expect(screen.getByText(/02:00/)).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByText(/01:59/)).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("rate_limited with null retryAfterSeconds renders daily-cap variant", () => {
    render(<RefusalBubble turn={makeTurn("rate_limited", null)} />);
    expect(screen.getByText(/today's chat limit/i)).toBeInTheDocument();
  });
});
