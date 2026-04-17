import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import React from "react";
import { MilestoneFeedbackCard } from "../components/MilestoneFeedbackCard";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

// Capture the most recent motion.div props so tests can drive onDragEnd
// synthetically (jsdom can't dispatch the pointer sequence motion/react needs).
const MOTION_HTML_PROPS = new Set([
  "children",
  "className",
  "id",
  "style",
  "tabIndex",
  "role",
  "onClick",
  "onKeyDown",
  "aria-label",
  "data-testid",
]);
const capturedMotionProps: { onDragEnd?: (e: unknown, info: { offset: { x: number; y: number } }) => void } = {};

vi.mock("motion/react", () => ({
  motion: {
    div: (props: Record<string, unknown>) => {
      capturedMotionProps.onDragEnd = props.onDragEnd as typeof capturedMotionProps.onDragEnd;
      const htmlProps: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(props)) {
        if (MOTION_HTML_PROPS.has(k) || k.startsWith("aria-") || k.startsWith("data-")) {
          htmlProps[k] = v;
        }
      }
      return React.createElement("div", htmlProps, props.children as React.ReactNode);
    },
  },
  useReducedMotion: () => false,
}));

describe("MilestoneFeedbackCard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    capturedMotionProps.onDragEnd = undefined;
  });

  it("renders emoji_rating variant with three emoji buttons", () => {
    render(
      <MilestoneFeedbackCard
        cardType="milestone_3rd_upload"
        onRespond={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    expect(screen.getByTestId("emoji-happy")).toBeInTheDocument();
    expect(screen.getByTestId("emoji-neutral")).toBeInTheDocument();
    expect(screen.getByTestId("emoji-sad")).toBeInTheDocument();
    expect(screen.getByText("thirdUploadTitle")).toBeInTheDocument();
  });

  it("renders yes_no variant with yes and no buttons", () => {
    render(
      <MilestoneFeedbackCard
        cardType="health_score_change"
        onRespond={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    expect(screen.getByTestId("response-yes")).toBeInTheDocument();
    expect(screen.getByTestId("response-no")).toBeInTheDocument();
    expect(screen.getByText("healthScoreTitle")).toBeInTheDocument();
    expect(screen.queryByTestId("emoji-happy")).not.toBeInTheDocument();
  });

  it("calls onRespond with correct value when emoji is selected and submit tapped", () => {
    const onRespond = vi.fn();
    render(
      <MilestoneFeedbackCard
        cardType="milestone_3rd_upload"
        onRespond={onRespond}
        onDismiss={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByTestId("emoji-happy"));
    fireEvent.click(screen.getByTestId("milestone-submit"));

    expect(onRespond).toHaveBeenCalledWith("happy", undefined);
  });

  it("calls onRespond with free_text when provided", () => {
    const onRespond = vi.fn();
    render(
      <MilestoneFeedbackCard
        cardType="milestone_3rd_upload"
        onRespond={onRespond}
        onDismiss={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByTestId("emoji-happy"));
    fireEvent.change(screen.getByPlaceholderText("optionalComment"), {
      target: { value: "Great app" },
    });
    fireEvent.click(screen.getByTestId("milestone-submit"));

    expect(onRespond).toHaveBeenCalledWith("happy", "Great app");
  });

  it("calls onDismiss when skip tapped", () => {
    const onDismiss = vi.fn();
    render(
      <MilestoneFeedbackCard
        cardType="milestone_3rd_upload"
        onRespond={vi.fn()}
        onDismiss={onDismiss}
      />,
    );

    fireEvent.click(screen.getByTestId("milestone-skip"));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("submit button calls onRespond with yes/no selection", () => {
    const onRespond = vi.fn();
    render(
      <MilestoneFeedbackCard
        cardType="health_score_change"
        onRespond={onRespond}
        onDismiss={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByTestId("response-yes"));
    fireEvent.click(screen.getByTestId("milestone-submit"));

    expect(onRespond).toHaveBeenCalledWith("yes", undefined);
  });

  it("calls onDismiss when horizontal drag exceeds swipe threshold (AC #3)", () => {
    const onDismiss = vi.fn();
    render(
      <MilestoneFeedbackCard
        cardType="milestone_3rd_upload"
        onRespond={vi.fn()}
        onDismiss={onDismiss}
      />,
    );

    // Drag past the 80px threshold (left) — dismiss fires.
    capturedMotionProps.onDragEnd?.({}, { offset: { x: -120, y: 0 } });
    expect(onDismiss).toHaveBeenCalledTimes(1);

    // Drag past threshold the other direction also dismisses.
    capturedMotionProps.onDragEnd?.({}, { offset: { x: 120, y: 0 } });
    expect(onDismiss).toHaveBeenCalledTimes(2);
  });

  it("does NOT dismiss when drag is below swipe threshold", () => {
    const onDismiss = vi.fn();
    render(
      <MilestoneFeedbackCard
        cardType="milestone_3rd_upload"
        onRespond={vi.fn()}
        onDismiss={onDismiss}
      />,
    );

    capturedMotionProps.onDragEnd?.({}, { offset: { x: -40, y: 0 } });
    capturedMotionProps.onDragEnd?.({}, { offset: { x: 40, y: 0 } });
    expect(onDismiss).not.toHaveBeenCalled();
  });

  it("submit is disabled until a value is selected", () => {
    render(
      <MilestoneFeedbackCard
        cardType="milestone_3rd_upload"
        onRespond={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    const submit = screen.getByTestId("milestone-submit") as HTMLButtonElement;
    expect(submit.disabled).toBe(true);

    fireEvent.click(screen.getByTestId("emoji-neutral"));
    expect(submit.disabled).toBe(false);
  });
});
