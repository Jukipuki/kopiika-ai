import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  CardFeedbackBar,
  _sessionFlags,
} from "../components/CardFeedbackBar";

const mockSubmitVote = vi.fn();
const mockSubmitReasonChip = vi.fn();
const mockUseCardFeedback = vi.fn();

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: { accessToken: "test-token" }, status: "authenticated" }),
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("../hooks/use-card-feedback", () => ({
  useCardFeedback: (...args: unknown[]) => mockUseCardFeedback(...args),
}));

vi.mock("../components/ReportIssueForm", () => ({
  ReportIssueForm: ({ onClose }: { cardId: string; onClose: () => void }) => (
    <div data-testid="report-issue-form">
      <button type="button" onClick={onClose}>
        close-form
      </button>
    </div>
  ),
}));

vi.mock("../components/FollowUpPanel", () => ({
  FollowUpPanel: ({
    onDismiss,
    onChipSelect,
  }: {
    onDismiss: () => void;
    onChipSelect?: (chip: string) => void;
  }) => (
    <div data-testid="follow-up-panel">
      <button type="button" onClick={onDismiss}>
        dismiss-panel
      </button>
      <button type="button" onClick={() => onChipSelect?.("not_relevant")}>
        pick-chip
      </button>
    </div>
  ),
}));

// Mock DropdownMenu (base-ui portals are awkward in jsdom). Render the menu
// inline so tests can click the trigger and the item without portals.
vi.mock("@/components/ui/dropdown-menu", () => {
  const DropdownMenu = ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dropdown-menu">{children}</div>
  );
  const DropdownMenuTrigger = ({
    children,
    render: _render,
    ...rest
  }: {
    render?: React.ReactElement;
    children?: React.ReactNode;
    [key: string]: unknown;
  }) => (
    <button type="button" {...rest}>
      {children}
    </button>
  );
  const DropdownMenuContent = ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dropdown-menu-content">{children}</div>
  );
  const DropdownMenuItem = ({
    children,
    onClick,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
  }) => (
    <button type="button" onClick={onClick}>
      {children}
    </button>
  );
  return {
    DropdownMenu,
    DropdownMenuTrigger,
    DropdownMenuContent,
    DropdownMenuItem,
  };
});

describe("CardFeedbackBar", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockUseCardFeedback.mockReturnValue({
      vote: null,
      submitVote: mockSubmitVote,
      isPending: false,
      feedbackId: "feedback-uuid-123",
      submitReasonChip: mockSubmitReasonChip,
      isReasonChipPending: false,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    mockSubmitVote.mockReset();
    mockSubmitReasonChip.mockReset();
    mockUseCardFeedback.mockReset();
    _sessionFlags.hasShownFollowUp = false;
  });

  it("does not render icons before 2 seconds", () => {
    render(<CardFeedbackBar cardId="card-1" />);
    expect(screen.queryByLabelText("Rate this insight helpful")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Rate this insight not helpful")).not.toBeInTheDocument();
  });

  it("renders thumb icons after 2 seconds", () => {
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(screen.getByLabelText("Rate this insight helpful")).toBeInTheDocument();
    expect(screen.getByLabelText("Rate this insight not helpful")).toBeInTheDocument();
  });

  it("calls submitVote('up') on thumbs-up click", () => {
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    fireEvent.click(screen.getByLabelText("Rate this insight helpful"));
    expect(mockSubmitVote).toHaveBeenCalledWith("up");
  });

  it("calls submitVote('down') on thumbs-down click", () => {
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    fireEvent.click(screen.getByLabelText("Rate this insight not helpful"));
    expect(mockSubmitVote).toHaveBeenCalledWith("down");
  });

  it("does not call submitVote when already voted same direction", () => {
    mockUseCardFeedback.mockReturnValue({
      vote: "up",
      submitVote: mockSubmitVote,
      isPending: false,
      feedbackId: "feedback-uuid-123",
      submitReasonChip: mockSubmitReasonChip,
      isReasonChipPending: false,
    });
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    fireEvent.click(screen.getByLabelText("Rate this insight helpful"));
    expect(mockSubmitVote).not.toHaveBeenCalled();
  });

  it("allows voting opposite direction when already voted", () => {
    mockUseCardFeedback.mockReturnValue({
      vote: "up",
      submitVote: mockSubmitVote,
      isPending: false,
      feedbackId: "feedback-uuid-123",
      submitReasonChip: mockSubmitReasonChip,
      isReasonChipPending: false,
    });
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    fireEvent.click(screen.getByLabelText("Rate this insight not helpful"));
    expect(mockSubmitVote).toHaveBeenCalledWith("down");
  });

  it("sets aria-pressed correctly based on vote state", () => {
    mockUseCardFeedback.mockReturnValue({
      vote: "up",
      submitVote: mockSubmitVote,
      isPending: false,
      feedbackId: "feedback-uuid-123",
      submitReasonChip: mockSubmitReasonChip,
      isReasonChipPending: false,
    });
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(screen.getByLabelText("Rate this insight helpful")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Rate this insight not helpful")).toHaveAttribute("aria-pressed", "false");
  });

  it("disables buttons when isPending", () => {
    mockUseCardFeedback.mockReturnValue({
      vote: null,
      submitVote: mockSubmitVote,
      isPending: true,
      feedbackId: "feedback-uuid-123",
      submitReasonChip: mockSubmitReasonChip,
      isReasonChipPending: false,
    });
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(screen.getByLabelText("Rate this insight helpful")).toBeDisabled();
    expect(screen.getByLabelText("Rate this insight not helpful")).toBeDisabled();
  });

  it("renders the overflow menu trigger", () => {
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(screen.getByLabelText("openMenu")).toBeInTheDocument();
  });

  it("does not render ReportIssueForm by default", () => {
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(screen.queryByTestId("report-issue-form")).not.toBeInTheDocument();
  });

  it("opens ReportIssueForm when 'Report an issue' menu item is clicked (AC #1)", () => {
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.queryByTestId("report-issue-form")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("trigger"));
    expect(screen.getByTestId("report-issue-form")).toBeInTheDocument();
  });

  it("closes ReportIssueForm when its onClose is invoked", () => {
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    fireEvent.click(screen.getByText("trigger"));
    expect(screen.getByTestId("report-issue-form")).toBeInTheDocument();

    fireEvent.click(screen.getByText("close-form"));
    expect(screen.queryByTestId("report-issue-form")).not.toBeInTheDocument();
  });

  // ── Follow-up panel (Story 7.5) ──────────────────────────────────────

  it("does not render FollowUpPanel immediately after thumbs-down (AC #1: 300ms delay)", () => {
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    fireEvent.click(screen.getByLabelText("Rate this insight not helpful"));
    expect(screen.queryByTestId("follow-up-panel")).not.toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(screen.queryByTestId("follow-up-panel")).not.toBeInTheDocument();
  });

  it("renders FollowUpPanel 300ms after thumbs-down (AC #1)", () => {
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    fireEvent.click(screen.getByLabelText("Rate this insight not helpful"));
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.getByTestId("follow-up-panel")).toBeInTheDocument();
  });

  it("does NOT render FollowUpPanel on thumbs-up", () => {
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    fireEvent.click(screen.getByLabelText("Rate this insight helpful"));
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.queryByTestId("follow-up-panel")).not.toBeInTheDocument();
  });

  it("only shows FollowUpPanel on the first thumbs-down of the session (AC #4)", () => {
    const { unmount } = render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    fireEvent.click(screen.getByLabelText("Rate this insight not helpful"));
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.getByTestId("follow-up-panel")).toBeInTheDocument();
    unmount();

    // Fresh instance, another thumbs-down — panel should NOT appear again.
    render(<CardFeedbackBar cardId="card-2" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    fireEvent.click(screen.getByLabelText("Rate this insight not helpful"));
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(screen.queryByTestId("follow-up-panel")).not.toBeInTheDocument();
  });

  it("hides FollowUpPanel when its onDismiss is invoked (AC #3)", () => {
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    fireEvent.click(screen.getByLabelText("Rate this insight not helpful"));
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.getByTestId("follow-up-panel")).toBeInTheDocument();

    fireEvent.click(screen.getByText("dismiss-panel"));
    expect(screen.queryByTestId("follow-up-panel")).not.toBeInTheDocument();
  });

  it("forwards chip selection to submitReasonChip (AC #2)", () => {
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    fireEvent.click(screen.getByLabelText("Rate this insight not helpful"));
    act(() => {
      vi.advanceTimersByTime(300);
    });

    fireEvent.click(screen.getByText("pick-chip"));
    expect(mockSubmitReasonChip).toHaveBeenCalledWith("not_relevant");
  });

  it("does not render FollowUpPanel when feedbackId is not yet known", () => {
    mockUseCardFeedback.mockReturnValue({
      vote: null,
      submitVote: mockSubmitVote,
      isPending: false,
      feedbackId: null,
      submitReasonChip: mockSubmitReasonChip,
      isReasonChipPending: false,
    });
    render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    fireEvent.click(screen.getByLabelText("Rate this insight not helpful"));
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.queryByTestId("follow-up-panel")).not.toBeInTheDocument();
  });

  it("defers session flag until feedbackId is known (H1 race fix)", () => {
    // Round 1: vote POST is slow — feedbackId not available at 300ms.
    mockUseCardFeedback.mockReturnValue({
      vote: null,
      submitVote: mockSubmitVote,
      isPending: false,
      feedbackId: null,
      submitReasonChip: mockSubmitReasonChip,
      isReasonChipPending: false,
    });
    const { unmount } = render(<CardFeedbackBar cardId="card-1" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    fireEvent.click(screen.getByLabelText("Rate this insight not helpful"));
    act(() => {
      vi.advanceTimersByTime(300);
    });
    // feedbackId was null: panel not shown AND flag NOT consumed.
    expect(screen.queryByTestId("follow-up-panel")).not.toBeInTheDocument();
    expect(_sessionFlags.hasShownFollowUp).toBe(false);
    unmount();

    // Round 2: fresh card with feedbackId available → panel SHOULD show
    // (flag was not consumed in round 1).
    mockUseCardFeedback.mockReturnValue({
      vote: null,
      submitVote: mockSubmitVote,
      isPending: false,
      feedbackId: "feedback-uuid-123",
      submitReasonChip: mockSubmitReasonChip,
      isReasonChipPending: false,
    });
    render(<CardFeedbackBar cardId="card-2" />);
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    fireEvent.click(screen.getByLabelText("Rate this insight not helpful"));
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.getByTestId("follow-up-panel")).toBeInTheDocument();
  });
});
