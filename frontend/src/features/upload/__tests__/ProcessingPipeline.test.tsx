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
  it("renders all 5 stages (8.3)", () => {
    render(
      <ProcessingPipeline
        status="processing"
        step="ingestion"
        progress={10}
        error={null}
      />,
    );

    expect(screen.getByText("Reading your transactions...")).toBeInTheDocument();
    expect(screen.getByText("Categorizing your spending...")).toBeInTheDocument();
    expect(screen.getByText("Detecting patterns...")).toBeInTheDocument();
    expect(screen.getByText("Scoring your financial health...")).toBeInTheDocument();
    expect(screen.getByText("Generating personalized insights...")).toBeInTheDocument();
  });

  it("shows active stage with educational content", () => {
    render(
      <ProcessingPipeline
        status="processing"
        step="ingestion"
        progress={10}
        error={null}
      />,
    );

    // First stage active → shows educational content
    expect(
      screen.getByText("We're securely reading each transaction from your statement"),
    ).toBeInTheDocument();
  });

  it("shows completed state with checkmark", () => {
    render(
      <ProcessingPipeline
        status="completed"
        step={null}
        progress={100}
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
        error={null}
      />,
    );

    const progressbar = screen.getByRole("progressbar");
    expect(progressbar).toBeInTheDocument();
    expect(progressbar).toHaveAttribute("aria-valuenow", "1");
    expect(progressbar).toHaveAttribute("aria-valuemax", "5");
  });

  it("has aria-live polite for stage transitions (8.5)", () => {
    const { container } = render(
      <ProcessingPipeline
        status="processing"
        step="ingestion"
        progress={10}
        error={null}
      />,
    );

    const liveRegion = container.querySelector('[aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();
  });
});
