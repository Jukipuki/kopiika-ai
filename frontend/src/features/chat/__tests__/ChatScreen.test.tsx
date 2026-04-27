import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { createUseTranslations } from "@/test-utils/intl-mock";
import type { CitationDto } from "../lib/chat-types";

vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: { accessToken: "tok" }, status: "authenticated" }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ back: vi.fn() }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

// Inject a controllable stream so we can drive the FSM frame-by-frame.
const dispatchSend = vi.fn();
const turns: unknown[] = [];
let inFlight = false;
vi.mock("../hooks/useChatStream", () => ({
  useChatStream: () => ({
    turns,
    inFlight,
    send: dispatchSend,
    retryLast: vi.fn(),
    reset: vi.fn(),
  }),
}));

vi.mock("../hooks/useChatSession", () => ({
  useChatSession: () => ({
    sessions: [],
    isLoading: false,
    activeSessionId: "s1",
    selectSession: vi.fn(),
    createSession: vi.fn().mockResolvedValue({ sessionId: "s1", createdAt: "x" }),
    isCreating: false,
    createError: null,
    deleteSession: vi.fn(),
    isDeleting: false,
    bulkDeleteAll: vi.fn(),
    isBulkDeleting: false,
  }),
  useChatMessages: () => ({ data: { pages: [] }, isLoading: false }),
}));

vi.mock("../hooks/useChatConsent", () => ({
  useChatConsent: () => ({
    isLoading: false,
    consent: { hasCurrentConsent: true, version: "v1", grantedAt: "2026-04-01", locale: "en" },
    hasCurrentConsent: true,
    grant: vi.fn(),
    isGranting: false,
    revoke: vi.fn(),
    isRevoking: false,
  }),
  CHAT_PROCESSING: "chat_processing",
}));

if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: () => ({
      matches: false,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  });
}
if (typeof Element !== "undefined" && !Element.prototype.scrollTo) {
  Element.prototype.scrollTo = vi.fn() as unknown as typeof Element.prototype.scrollTo;
}

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ChatScreen happy path", () => {
  beforeEach(() => {
    turns.length = 0;
    inFlight = false;
    dispatchSend.mockReset();
  });

  it("renders empty hint, accepts user input, calls stream.send", async () => {
    const user = userEvent.setup();
    const { ChatScreen } = await import("../components/ChatScreen");
    wrap(<ChatScreen privacyHref="/en/settings" />);
    expect(screen.getByText(/ask a question/i)).toBeInTheDocument();
    const ta = screen.getByPlaceholderText(/finances/i);
    await user.type(ta, "How much did I spend on coffee?");
    await user.keyboard("{Enter}");
    expect(dispatchSend).toHaveBeenCalledWith("How much did I spend on coffee?");
  });

  it("renders citation chips when assistant turn carries citations", async () => {
    const cites: CitationDto[] = [
      {
        kind: "transaction",
        id: "tx1",
        bookedAt: "2026-03-14",
        description: "Coffee Shop",
        amountKopiykas: -8500,
        currency: "UAH",
        categoryCode: "groceries",
        label: "Coffee Shop · 2026-03-14",
      },
      { kind: "category", code: "groceries", label: "Groceries" },
    ];
    turns.push({
      id: "u1",
      role: "user",
      text: "What about groceries?",
      createdAt: "2026-04-26T10:00:00Z",
    });
    turns.push({
      id: "a1",
      role: "assistant",
      text: "You spent 85 UAH at Coffee Shop on March 14.",
      createdAt: "2026-04-26T10:00:01Z",
      streaming: false,
      citations: cites,
    });
    const { ChatScreen } = await import("../components/ChatScreen");
    wrap(<ChatScreen privacyHref="/en/settings" />);
    expect(screen.getByText(/Coffee Shop · 2026-03-14/)).toBeInTheDocument();
    expect(screen.getByText(/Groceries/)).toBeInTheDocument();
  });
});
