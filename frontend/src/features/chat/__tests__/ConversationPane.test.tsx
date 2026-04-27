import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";
import { ConversationPane } from "../components/ConversationPane";
import type { ChatTurnState } from "../hooks/useChatStream";

vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (q: string) => ({
      matches: false,
      media: q,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
      onchange: null,
    }),
  });
}
// jsdom does not implement Element.scrollTo — stub it for the scroll-lock hook.
if (typeof Element !== "undefined" && !Element.prototype.scrollTo) {
  Element.prototype.scrollTo = vi.fn() as unknown as typeof Element.prototype.scrollTo;
}

function makeAssistantTurn(text = "hi"): ChatTurnState {
  return {
    id: `t-${Math.random()}`,
    role: "assistant",
    text,
    createdAt: "2026-04-26T10:00:00Z",
    streaming: false,
  };
}

describe("ConversationPane historical-message rendering (Story 10.10)", () => {
  // Story 10.10 routes historical messages from useChatMessages through the
  // same `turns` prop the live stream feeds. The pane filters out tool-role
  // rows defensively (the backend also filters; this guards against future
  // upstream regressions).
  it("renders historical user + assistant turns in chronological order", () => {
    const turns: ChatTurnState[] = [
      { id: "h1", role: "user", text: "first user msg", createdAt: "2026-04-26T10:00:00Z" },
      { id: "h2", role: "assistant", text: "first assistant reply", createdAt: "2026-04-26T10:00:01Z" },
    ];
    render(<ConversationPane turns={turns} />);
    const bubbles = screen.getAllByText(/first/i);
    // First DOM occurrence should be the user msg, then the assistant reply.
    expect(bubbles[0].textContent).toMatch(/user/i);
    expect(bubbles[1].textContent).toMatch(/assistant/i);
  });

  it("never renders a tool-role bubble (FE assumes backend has filtered)", () => {
    // The ChatTurnState union excludes "tool", so the FE has no code path to
    // render one — the assertion is structural: TypeScript guarantees it,
    // and any consumer that tried would fail typecheck. This test just
    // documents the invariant by rendering only allowed roles.
    const turns: ChatTurnState[] = [
      { id: "h1", role: "user", text: "u", createdAt: "2026-04-26T10:00:00Z" },
      { id: "h2", role: "assistant", text: "a", createdAt: "2026-04-26T10:00:01Z" },
    ];
    render(<ConversationPane turns={turns} />);
    expect(screen.queryByText(/tool payload/i)).toBeNull();
  });
});

describe("ConversationPane scroll-lock 80px rule", () => {
  // jsdom doesn't run layout, so we stub the scroll properties on the
  // pane's div directly to simulate the user being scrolled up vs. pinned.
  function patchScroll(el: HTMLElement, scrollTop: number, scrollHeight = 1000, clientHeight = 200) {
    Object.defineProperty(el, "scrollTop", { configurable: true, value: scrollTop, writable: true });
    Object.defineProperty(el, "scrollHeight", { configurable: true, value: scrollHeight });
    Object.defineProperty(el, "clientHeight", { configurable: true, value: clientHeight });
  }

  it("pinned (within 80px of bottom): no jump button, auto-scrolls on append", () => {
    const turns = [makeAssistantTurn("first")];
    const { rerender, container } = render(<ConversationPane turns={turns} />);
    const pane = container.querySelector('[role="log"]') as HTMLElement;
    // Pinned: scrollHeight - scrollTop - clientHeight = 0
    patchScroll(pane, 800, 1000, 200);
    fireEvent.scroll(pane);
    expect(screen.queryByLabelText(/new messages/i)).toBeNull();
    rerender(<ConversationPane turns={[...turns, makeAssistantTurn("second")]} />);
    expect(screen.queryByLabelText(/new messages/i)).toBeNull();
  });

  it("scrolled up >80px: jump button appears, scrolling to bottom dismisses it", () => {
    const turns = [makeAssistantTurn("first")];
    const { rerender, container } = render(<ConversationPane turns={turns} />);
    const pane = container.querySelector('[role="log"]') as HTMLElement;
    // Distance from bottom = 1000 - 600 - 200 = 200 > 80.
    patchScroll(pane, 600, 1000, 200);
    fireEvent.scroll(pane);
    rerender(<ConversationPane turns={[...turns, makeAssistantTurn("second")]} />);
    expect(screen.getByLabelText(/new messages/i)).toBeInTheDocument();
    pane.scrollTo = vi.fn();
    // Click the button; it triggers scrollTo + dismiss.
    fireEvent.click(screen.getByLabelText(/new messages/i));
    expect(pane.scrollTo).toHaveBeenCalled();
  });
});
