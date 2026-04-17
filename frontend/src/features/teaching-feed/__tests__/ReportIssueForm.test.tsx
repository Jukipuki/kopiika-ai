import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ReportIssueForm } from "../components/ReportIssueForm";

const mockSubmitReport = vi.fn();
const mockUseIssueReport = vi.fn();

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, values?: Record<string, unknown>) =>
    values ? `${key} ${JSON.stringify(values)}` : key,
}));

vi.mock("../hooks/use-issue-report", () => ({
  useIssueReport: (...args: unknown[]) => mockUseIssueReport(...args),
}));

// Mock base-ui Select (renders in a portal, awkward in jsdom). Expose a
// `data-testid="category-select"` with native <select> semantics so tests can
// drive the `onValueChange` path directly.
vi.mock("@/components/ui/select", () => {
  const Select = ({
    value,
    onValueChange,
    children,
  }: {
    value?: string;
    onValueChange: (v: string) => void;
    children: React.ReactNode;
  }) => (
    <select
      data-testid="category-select"
      value={value ?? ""}
      onChange={(e) => onValueChange(e.target.value)}
    >
      <option value="" disabled>
        placeholder
      </option>
      {children}
    </select>
  );
  const SelectTrigger = ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  );
  const SelectValue = () => null;
  const SelectContent = ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  );
  const SelectItem = ({
    value,
    children,
  }: {
    value: string;
    children: React.ReactNode;
  }) => <option value={value}>{children}</option>;
  return { Select, SelectTrigger, SelectValue, SelectContent, SelectItem };
});

describe("ReportIssueForm", () => {
  beforeEach(() => {
    mockUseIssueReport.mockReturnValue({
      submitReport: mockSubmitReport,
      isPending: false,
      isAlreadyReported: false,
      confirmationShown: false,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    mockSubmitReport.mockReset();
    mockUseIssueReport.mockReset();
  });

  it("disables submit when no category selected", () => {
    const onClose = vi.fn();
    render(<ReportIssueForm cardId="c1" onClose={onClose} />);
    const submitBtn = screen.getByText("submit").closest("button");
    expect(submitBtn).toBeDisabled();
  });

  it("calls onClose when cancel button clicked", () => {
    const onClose = vi.fn();
    render(<ReportIssueForm cardId="c1" onClose={onClose} />);
    fireEvent.click(screen.getByText("cancel"));
    expect(onClose).toHaveBeenCalled();
  });

  it("renders confirmation message when confirmationShown=true", () => {
    mockUseIssueReport.mockReturnValue({
      submitReport: mockSubmitReport,
      isPending: false,
      isAlreadyReported: false,
      confirmationShown: true,
    });
    render(<ReportIssueForm cardId="c1" onClose={vi.fn()} />);
    expect(screen.getByText("success")).toBeInTheDocument();
    expect(screen.queryByText("submit")).not.toBeInTheDocument();
  });

  it("auto-closes 2s after confirmationShown becomes true", () => {
    vi.useFakeTimers();
    const onClose = vi.fn();
    mockUseIssueReport.mockReturnValue({
      submitReport: mockSubmitReport,
      isPending: false,
      isAlreadyReported: false,
      confirmationShown: true,
    });
    render(<ReportIssueForm cardId="c1" onClose={onClose} />);
    expect(onClose).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(onClose).toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("renders already-reported message when isAlreadyReported=true", () => {
    mockUseIssueReport.mockReturnValue({
      submitReport: mockSubmitReport,
      isPending: false,
      isAlreadyReported: true,
      confirmationShown: false,
    });
    render(<ReportIssueForm cardId="c1" onClose={vi.fn()} />);
    expect(screen.getByText("alreadyReported")).toBeInTheDocument();
    expect(screen.queryByText("submit")).not.toBeInTheDocument();
  });

  it("renders free-text toggle collapsed by default", () => {
    render(<ReportIssueForm cardId="c1" onClose={vi.fn()} />);
    expect(screen.getByText("freeText.toggle")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("freeText.placeholder")).not.toBeInTheDocument();
  });

  it("expands textarea when toggle clicked", () => {
    render(<ReportIssueForm cardId="c1" onClose={vi.fn()} />);
    fireEvent.click(screen.getByText("freeText.toggle"));
    expect(screen.getByPlaceholderText("freeText.placeholder")).toBeInTheDocument();
  });

  it("submits report with selected category and free text (AC #3)", () => {
    const onClose = vi.fn();
    render(<ReportIssueForm cardId="c1" onClose={onClose} />);

    const select = screen.getByTestId("category-select") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "bug" } });

    fireEvent.click(screen.getByText("freeText.toggle"));
    const textarea = screen.getByPlaceholderText(
      "freeText.placeholder",
    ) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "amount mismatch" } });

    const submitBtn = screen.getByText("submit").closest("button");
    expect(submitBtn).not.toBeDisabled();
    fireEvent.click(submitBtn!);

    expect(mockSubmitReport).toHaveBeenCalledWith({
      issueCategory: "bug",
      freeText: "amount mismatch",
    });
  });

  it("submits with undefined freeText when details are not expanded (AC #3)", () => {
    render(<ReportIssueForm cardId="c1" onClose={vi.fn()} />);

    fireEvent.change(screen.getByTestId("category-select"), {
      target: { value: "other" },
    });
    fireEvent.click(screen.getByText("submit").closest("button")!);

    expect(mockSubmitReport).toHaveBeenCalledWith({
      issueCategory: "other",
      freeText: undefined,
    });
  });
});
