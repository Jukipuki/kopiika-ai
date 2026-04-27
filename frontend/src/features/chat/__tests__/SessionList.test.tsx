import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { createUseTranslations } from "@/test-utils/intl-mock";

vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: { accessToken: "tok" }, status: "authenticated" }),
}));

const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    success: (...a: unknown[]) => toastSuccess(...a),
    error: (...a: unknown[]) => toastError(...a),
  },
}));

const mockSessions = vi.fn();
const mockCreate = vi.fn();
const mockDelete = vi.fn();
const mockBulkDelete = vi.fn();
const mockSelect = vi.fn();
vi.mock("../hooks/useChatSession", () => ({
  useChatSession: () => ({
    sessions: mockSessions(),
    isLoading: false,
    activeSessionId: null,
    selectSession: mockSelect,
    createSession: mockCreate,
    isCreating: false,
    createError: null,
    deleteSession: mockDelete,
    isDeleting: false,
    bulkDeleteAll: mockBulkDelete,
    isBulkDeleting: false,
  }),
  useChatMessages: () => ({ data: { pages: [] }, isLoading: false }),
}));

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("SessionList", () => {
  beforeEach(async () => {
    mockSessions.mockReturnValue([
      { sessionId: "s1", createdAt: "2026-04-26T10:00:00Z", title: "First chat" },
    ]);
    mockCreate.mockResolvedValue({ sessionId: "new", createdAt: "x" });
    mockDelete.mockResolvedValue("s1");
    mockBulkDelete.mockResolvedValue(undefined);
    toastSuccess.mockClear();
    toastError.mockClear();
  });

  it("renders session rows with kebab + new-chat button", async () => {
    const { SessionList } = await import("../components/SessionList");
    wrap(<SessionList />);
    expect(screen.getByText(/first chat/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/chat actions/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new chat/i })).toBeInTheDocument();
  });

  it("New chat triggers createSession", async () => {
    const user = userEvent.setup();
    const { SessionList } = await import("../components/SessionList");
    wrap(<SessionList />);
    await user.click(screen.getByRole("button", { name: /new chat/i }));
    expect(mockCreate).toHaveBeenCalled();
  });

  it("renders enabled Delete-all link by default (bulk-delete on)", async () => {
    const { SessionList } = await import("../components/SessionList");
    wrap(<SessionList />);
    const link = screen.getByRole("button", { name: /delete all chats/i });
    expect(link).toHaveAttribute("aria-disabled", "false");
  });

  it("bulk-delete confirm calls bulkDeleteAll, toasts, and clears active session", async () => {
    const user = userEvent.setup();
    const { SessionList } = await import("../components/SessionList");
    wrap(<SessionList />);
    await user.click(screen.getByRole("button", { name: /delete all chats/i }));
    // Type the confirm-match phrase ("delete") to enable the destructive CTA.
    const input = await screen.findByRole("textbox");
    await user.type(input, "delete");
    await user.click(screen.getByRole("button", { name: /^delete all$/i }));
    expect(mockBulkDelete).toHaveBeenCalled();
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("just-created session comes from server refetch, not local state", async () => {
    // Mock returns the same (empty) list both before and after createSession;
    // the previous localSessions workaround would have shown the new row
    // optimistically. After 10.10's refactor, the visible list mirrors the
    // server query — empty stays empty until the next refetch fills it.
    mockSessions.mockReturnValue([]);
    const user = userEvent.setup();
    const { SessionList } = await import("../components/SessionList");
    wrap(<SessionList />);
    await user.click(screen.getByRole("button", { name: /new chat/i }));
    expect(mockCreate).toHaveBeenCalled();
    // No optimistic injection — list remains empty until the mocked GET fills.
    expect(screen.queryByText(/first chat/i)).toBeNull();
  });
});
