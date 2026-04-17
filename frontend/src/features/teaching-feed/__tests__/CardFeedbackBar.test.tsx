import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { CardFeedbackBar } from "../components/CardFeedbackBar";

const mockSubmitVote = vi.fn();
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
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    mockSubmitVote.mockReset();
    mockUseCardFeedback.mockReset();
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
});
