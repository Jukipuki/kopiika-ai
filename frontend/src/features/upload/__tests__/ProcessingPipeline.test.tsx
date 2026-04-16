import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";
import ProcessingPipeline from "../components/ProcessingPipeline";

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

describe("ProcessingPipeline", () => {
  it("renders all 5 canonical stages (Story 2.8)", () => {
    render(
      <ProcessingPipeline
        status="processing"
        step="ingestion"
        progress={10}
        message={null}
        error={null}
      />,
    );

    expect(screen.getByText("Reading your transactions...")).toBeInTheDocument();
    expect(screen.getByText("Categorizing your spending...")).toBeInTheDocument();
    expect(screen.getByText("Detecting patterns...")).toBeInTheDocument();
    expect(screen.getByText("Prioritizing what matters...")).toBeInTheDocument();
    expect(screen.getByText("Generating personalized insights...")).toBeInTheDocument();
  });

  it("renders backend-driven message under the active stage (Story 2.8)", () => {
    render(
      <ProcessingPipeline
        status="processing"
        step="ingestion"
        progress={10}
        message="Reading transactions..."
        error={null}
      />,
    );

    expect(
      screen.getByText("Reading transactions..."),
    ).toBeInTheDocument();
  });

  it("falls back to localized fallbackMessage when message is null (Story 2.8)", () => {
    render(
      <ProcessingPipeline
        status="processing"
        step="ingestion"
        progress={10}
        message={null}
        error={null}
      />,
    );

    expect(screen.getByText("Processing...")).toBeInTheDocument();
  });

  it("shows completed state with checkmark", () => {
    render(
      <ProcessingPipeline
        status="completed"
        step={null}
        progress={100}
        message={null}
        error={null}
      />,
    );

    expect(screen.getByText("Processing complete!")).toBeInTheDocument();
  });

  it("shows error state with retry button (8.4)", async () => {
    const onRetry = vi.fn();
    render(
      <ProcessingPipeline
        status="failed"
        step={null}
        progress={0}
        message={null}
        error={{ code: "LLM_ERROR", message: "Failed" }}
        onRetry={onRetry}
      />,
    );

    expect(
      screen.getByText("We couldn't process this file. Please try again."),
    ).toBeInTheDocument();

    const retryButton = screen.getByRole("button", { name: "Try again" });
    expect(retryButton).toBeInTheDocument();

    await userEvent.click(retryButton);
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("has progressbar role with aria-valuenow (8.5)", () => {
    render(
      <ProcessingPipeline
        status="processing"
        step="ingestion"
        progress={10}
        message={null}
        error={null}
      />,
    );

    const progressbar = screen.getByRole("progressbar");
    expect(progressbar).toBeInTheDocument();
    expect(progressbar).toHaveAttribute("aria-valuenow", "1");
    expect(progressbar).toHaveAttribute("aria-valuemax", "5");
  });

  it("hides retry button when isRetryable is false (9.6)", () => {
    const onRetry = vi.fn();
    render(
      <ProcessingPipeline
        status="failed"
        step={null}
        progress={0}
        message={null}
        error={{ code: "LLM_ERROR", message: "Failed" }}
        onRetry={onRetry}
        isRetryable={false}
      />,
    );

    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("shows circuit breaker message when error code is SERVICE_UNAVAILABLE (9.8)", () => {
    render(
      <ProcessingPipeline
        status="failed"
        step={null}
        progress={0}
        message={null}
        error={{ code: "SERVICE_UNAVAILABLE", message: "Circuit open" }}
      />,
    );

    expect(
      screen.getByText("Processing is temporarily unavailable. Please try again in a few minutes."),
    ).toBeInTheDocument();
  });

  it("shows retrying message with attempt count (8.2)", () => {
    render(
      <ProcessingPipeline
        status="retrying"
        step="categorization"
        progress={40}
        message={null}
        error={null}
        retryCount={2}
      />,
    );

    expect(screen.getByText(/Retrying/)).toBeInTheDocument();
  });

  it("has aria-live polite for stage transitions (8.5)", () => {
    const { container } = render(
      <ProcessingPipeline
        status="processing"
        step="ingestion"
        progress={10}
        message={null}
        error={null}
      />,
    );

    const liveRegion = container.querySelector('[aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();
  });

  it("advances past pattern-detection/triage placeholders when backend skips them (Story 2.8 Phase 1.5)", () => {
    // When backend jumps from `categorization` to `profile`/`health-score`,
    // pattern-detection and triage should still render as done (checkmark).
    render(
      <ProcessingPipeline
        status="processing"
        step="profile"
        progress={90}
        message="Building your financial profile..."
        error={null}
      />,
    );

    // active index for "profile" is 3 (triage slot) → stages 0,1,2 are done
    const progressbar = screen.getByRole("progressbar");
    expect(progressbar).toHaveAttribute("aria-valuenow", "4");
  });
});
