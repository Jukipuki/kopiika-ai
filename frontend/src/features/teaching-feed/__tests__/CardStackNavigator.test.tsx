import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { CardStackNavigator } from "../components/CardStackNavigator";
import type { InsightCard } from "../types";

// HTML-safe attributes to forward to the rendered div
const HTML_PROPS = new Set([
  "children",
  "className",
  "id",
  "style",
  "tabIndex",
  "role",
  "onClick",
  "onKeyDown",
  "aria-label",
  "aria-live",
  "data-testid",
]);

// Capture the latest onDragEnd callback so tests can invoke it
let capturedDragEnd: ((event: unknown, info: { offset: { x: number } }) => void) | null = null;
let mockReducedMotion = false;

vi.mock("motion/react", () => ({
  motion: {
    div: (props: Record<string, unknown>) => {
      const htmlProps: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(props)) {
        if (HTML_PROPS.has(k) || k.startsWith("aria-") || k.startsWith("data-")) {
          htmlProps[k] = v;
        }
      }
      if (typeof props.onDragEnd === "function") {
        capturedDragEnd = props.onDragEnd as typeof capturedDragEnd;
      }
      return React.createElement("div", htmlProps, props.children as React.ReactNode);
    },
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
  useReducedMotion: () => mockReducedMotion,
}));

const mockCards: InsightCard[] = [
  {
    id: "uuid-1",
    uploadId: null,
    headline: "Card One Headline",
    keyMetric: "₴1,000",
    whyItMatters: "Reason one.",
    deepDive: "Deep one.",
    severity: "high",
    category: "food",
    createdAt: "2026-04-04T12:00:00.000000Z",
  },
  {
    id: "uuid-2",
    uploadId: null,
    headline: "Card Two Headline",
    keyMetric: "₴2,000",
    whyItMatters: "Reason two.",
    deepDive: "Deep two.",
    severity: "medium",
    category: "utilities",
    createdAt: "2026-04-04T12:00:00.000000Z",
  },
  {
    id: "uuid-3",
    uploadId: null,
    headline: "Card Three Headline",
    keyMetric: "₴3,000",
    whyItMatters: "Reason three.",
    deepDive: "Deep three.",
    severity: "low",
    category: "transport",
    createdAt: "2026-04-04T12:00:00.000000Z",
  },
];

describe("CardStackNavigator", () => {
  beforeEach(() => {
    mockReducedMotion = false;
    capturedDragEnd = null;
  });

  it("renders first card by default (index 0)", () => {
    render(<CardStackNavigator cards={mockCards} />);
    expect(screen.getByText("Card One Headline")).toBeInTheDocument();
  });

  it("Next button click advances to second card", () => {
    render(<CardStackNavigator cards={mockCards} />);
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    expect(screen.getByText("Card Two Headline")).toBeInTheDocument();
  });

  it("Prev button is disabled at first card (index 0)", () => {
    render(<CardStackNavigator cards={mockCards} />);
    expect(screen.getByRole("button", { name: /previous insight/i })).toBeDisabled();
  });

  it("Next button is disabled at last card", () => {
    render(<CardStackNavigator cards={mockCards} />);
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    expect(screen.getByRole("button", { name: /next insight/i })).toBeDisabled();
  });

  it("progress counter shows correct 'X of Y' value", () => {
    render(<CardStackNavigator cards={mockCards} />);
    expect(screen.getByText("1 of 3")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    expect(screen.getByText("2 of 3")).toBeInTheDocument();
  });

  it("keyboard ArrowRight navigates to next card", () => {
    render(<CardStackNavigator cards={mockCards} />);
    const container = screen.getByRole("region", { name: /insight card stack/i });
    fireEvent.keyDown(container, { key: "ArrowRight" });
    expect(screen.getByText("Card Two Headline")).toBeInTheDocument();
  });

  it("keyboard ArrowLeft navigates to previous card", () => {
    render(<CardStackNavigator cards={mockCards} />);
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    const container = screen.getByRole("region", { name: /insight card stack/i });
    fireEvent.keyDown(container, { key: "ArrowLeft" });
    expect(screen.getByText("Card One Headline")).toBeInTheDocument();
  });

  it("renders nothing when cards array is empty", () => {
    const { container } = render(<CardStackNavigator cards={[]} />);
    expect(container.firstChild).toBeNull();
  });

  // H1: Drag/swipe gesture tests (AC #1)
  it("swipe left (negative offset > 80px) advances to next card", () => {
    render(<CardStackNavigator cards={mockCards} />);
    expect(capturedDragEnd).not.toBeNull();
    act(() => capturedDragEnd!({}, { offset: { x: -100 } }));
    expect(screen.getByText("Card Two Headline")).toBeInTheDocument();
    expect(screen.getByText("2 of 3")).toBeInTheDocument();
  });

  it("swipe right (positive offset > 80px) navigates to previous card", () => {
    render(<CardStackNavigator cards={mockCards} />);
    // Advance to card 2 first
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    expect(screen.getByText("Card Two Headline")).toBeInTheDocument();

    act(() => capturedDragEnd!({}, { offset: { x: 100 } }));
    expect(screen.getByText("Card One Headline")).toBeInTheDocument();
    expect(screen.getByText("1 of 3")).toBeInTheDocument();
  });

  it("swipe below threshold (< 80px) does not navigate", () => {
    render(<CardStackNavigator cards={mockCards} />);
    act(() => capturedDragEnd!({}, { offset: { x: -50 } }));
    expect(screen.getByText("Card One Headline")).toBeInTheDocument();
    expect(screen.getByText("1 of 3")).toBeInTheDocument();
  });

  // H2: Reduced motion tests (AC #3)
  it("renders and navigates with reduced motion enabled", () => {
    mockReducedMotion = true;
    render(<CardStackNavigator cards={mockCards} />);
    expect(screen.getByText("Card One Headline")).toBeInTheDocument();
    // Button navigation still works
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    expect(screen.getByText("Card Two Headline")).toBeInTheDocument();
  });
});
