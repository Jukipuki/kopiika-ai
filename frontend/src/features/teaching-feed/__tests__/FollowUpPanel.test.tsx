import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { FollowUpPanel } from "../components/FollowUpPanel";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

describe("FollowUpPanel", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("renders all four chip buttons", () => {
    render(<FollowUpPanel onDismiss={vi.fn()} onChipSelect={vi.fn()} />);
    expect(screen.getByText("chip.notRelevant")).toBeInTheDocument();
    expect(screen.getByText("chip.alreadyKnew")).toBeInTheDocument();
    expect(screen.getByText("chip.seemsIncorrect")).toBeInTheDocument();
    expect(screen.getByText("chip.hardToUnderstand")).toBeInTheDocument();
  });

  it("calls onChipSelect with the chip value and auto-dismisses after 1s", () => {
    const onChipSelect = vi.fn();
    const onDismiss = vi.fn();
    render(<FollowUpPanel onDismiss={onDismiss} onChipSelect={onChipSelect} />);

    fireEvent.click(screen.getByText("chip.notRelevant"));
    expect(onChipSelect).toHaveBeenCalledWith("not_relevant");
    expect(onDismiss).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("dismisses when the user taps outside the panel (AC #3)", () => {
    const onChipSelect = vi.fn();
    const onDismiss = vi.fn();
    render(
      <div>
        <button type="button" data-testid="outside">outside</button>
        <FollowUpPanel onDismiss={onDismiss} onChipSelect={onChipSelect} />
      </div>,
    );

    fireEvent.pointerDown(screen.getByTestId("outside"));

    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(onChipSelect).not.toHaveBeenCalled();
  });

  it("does NOT dismiss when the user taps inside the panel", () => {
    const onDismiss = vi.fn();
    render(<FollowUpPanel onDismiss={onDismiss} onChipSelect={vi.fn()} />);

    const title = screen.getByText("thumbsDownTitle");
    fireEvent.pointerDown(title);

    expect(onDismiss).not.toHaveBeenCalled();
  });

  it("dismisses when Escape is pressed (AC #5: keyboard a11y)", () => {
    const onDismiss = vi.fn();
    render(<FollowUpPanel onDismiss={onDismiss} onChipSelect={vi.fn()} />);

    fireEvent.keyDown(document.body, { key: "Escape" });

    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("auto-focuses the first chip on mount (AC #5)", () => {
    render(<FollowUpPanel onDismiss={vi.fn()} onChipSelect={vi.fn()} />);
    const firstChip = screen.getByText("chip.notRelevant").closest("button");
    expect(firstChip).toHaveFocus();
  });

  it("ignores a second chip click after selection", () => {
    const onChipSelect = vi.fn();
    render(<FollowUpPanel onDismiss={vi.fn()} onChipSelect={onChipSelect} />);

    fireEvent.click(screen.getByText("chip.notRelevant"));
    fireEvent.click(screen.getByText("chip.alreadyKnew"));

    expect(onChipSelect).toHaveBeenCalledTimes(1);
    expect(onChipSelect).toHaveBeenCalledWith("not_relevant");
  });

  it("renders 3 thumbs-up chip buttons when variant='thumbs_up'", () => {
    render(<FollowUpPanel variant="thumbs_up" onDismiss={vi.fn()} />);
    expect(screen.getByText("chip.learnedSomething")).toBeInTheDocument();
    expect(screen.getByText("chip.actionable")).toBeInTheDocument();
    expect(screen.getByText("chip.wellExplained")).toBeInTheDocument();
    expect(screen.queryByText("chip.notRelevant")).not.toBeInTheDocument();
    expect(screen.queryByText("chip.alreadyKnew")).not.toBeInTheDocument();
    expect(screen.queryByText("chip.seemsIncorrect")).not.toBeInTheDocument();
    expect(screen.queryByText("chip.hardToUnderstand")).not.toBeInTheDocument();
  });

  it("renders 4 thumbs-down chip buttons by default (regression guard)", () => {
    render(<FollowUpPanel onDismiss={vi.fn()} />);
    expect(screen.getByText("chip.notRelevant")).toBeInTheDocument();
    expect(screen.getByText("chip.alreadyKnew")).toBeInTheDocument();
    expect(screen.getByText("chip.seemsIncorrect")).toBeInTheDocument();
    expect(screen.getByText("chip.hardToUnderstand")).toBeInTheDocument();
    expect(screen.queryByText("chip.learnedSomething")).not.toBeInTheDocument();
  });

  it("calls onChipSelect with thumbs-up chip value", () => {
    const onChipSelect = vi.fn();
    render(<FollowUpPanel variant="thumbs_up" onDismiss={vi.fn()} onChipSelect={onChipSelect} />);

    fireEvent.click(screen.getByText("chip.actionable"));
    expect(onChipSelect).toHaveBeenCalledWith("actionable");
  });

  it("shows thumbsUpTitle when variant='thumbs_up'", () => {
    render(<FollowUpPanel variant="thumbs_up" onDismiss={vi.fn()} />);
    expect(screen.getByText("thumbsUpTitle")).toBeInTheDocument();
  });

  it("auto-dismisses 1s after chip click in thumbs_up variant (AC #2: identical behavior)", () => {
    const onDismiss = vi.fn();
    render(
      <FollowUpPanel variant="thumbs_up" onDismiss={onDismiss} onChipSelect={vi.fn()} />,
    );

    fireEvent.click(screen.getByText("chip.actionable"));
    expect(onDismiss).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("dismisses on tap-outside in thumbs_up variant (AC #2: identical behavior)", () => {
    const onDismiss = vi.fn();
    render(
      <div>
        <button type="button" data-testid="outside">outside</button>
        <FollowUpPanel variant="thumbs_up" onDismiss={onDismiss} />
      </div>,
    );

    fireEvent.pointerDown(screen.getByTestId("outside"));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("dismisses on Escape in thumbs_up variant (AC #2: identical behavior)", () => {
    const onDismiss = vi.fn();
    render(<FollowUpPanel variant="thumbs_up" onDismiss={onDismiss} />);

    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
