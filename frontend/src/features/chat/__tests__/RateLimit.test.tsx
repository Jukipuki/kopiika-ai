import { render, screen, act, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";
import { RefusalBubble } from "../components/RefusalBubble";
import { ConcurrentSessionsDialog } from "../components/ConcurrentSessionsDialog";
import type { ChatTurnState } from "../hooks/useChatStream";

vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

function rateLimitedTurn(retryAfterSeconds: number | null): ChatTurnState {
  return {
    id: "rl-1",
    role: "assistant",
    text: "",
    createdAt: "2026-04-26T10:00:00Z",
    refusal: { reason: "rate_limited", correlationId: "deadbeef-1234-5678-9012-345678901234", retryAfterSeconds },
  };
}

describe("RateLimit countdown + Try-again CTA", () => {
  it("shows mm:ss and ticks down each second", () => {
    vi.useFakeTimers({ shouldAdvanceTime: false });
    render(<RefusalBubble turn={rateLimitedTurn(2)} onRetry={vi.fn()} />);
    expect(screen.getByText(/00:02/)).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByText(/00:01/)).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("surfaces Try-again CTA after the cooldown elapses", async () => {
    const onRetry = vi.fn();
    render(<RefusalBubble turn={rateLimitedTurn(1)} onRetry={onRetry} />);
    // Real timers (1s wait) — cheaper than wrestling with fake-timer +
    // setTimeout(0) flush + React state batching dance.
    const btn = await screen.findByRole("button", { name: /try again/i }, { timeout: 3000 });
    expect(btn).toBeInTheDocument();
  });

  it("daily-cap variant (no retryAfterSeconds) renders local-time wall-clock copy", () => {
    render(<RefusalBubble turn={rateLimitedTurn(null)} />);
    expect(screen.getByText(/today's chat limit/i)).toBeInTheDocument();
    // Local-time string includes a HH:MM-shaped substring.
    expect(screen.getByText(/\d{1,2}:\d{2}/)).toBeInTheDocument();
  });
});

describe("ConcurrentSessionsDialog", () => {
  it("renders the active sessions as a clickable picker", () => {
    const onPick = vi.fn();
    render(
      <ConcurrentSessionsDialog
        open={true}
        onOpenChange={() => undefined}
        sessions={[
          { sessionId: "a", createdAt: "x", title: "Alpha" },
          { sessionId: "b", createdAt: "x", title: "Bravo" },
        ]}
        onPickSession={onPick}
      />,
    );
    expect(screen.getByText(/too many chats open/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /alpha/i }));
    expect(onPick).toHaveBeenCalledWith("a");
  });
});
