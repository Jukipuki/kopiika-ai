import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { CardStackNavigator } from "../components/CardStackNavigator";
import type { InsightCard } from "../types";

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: null, status: "unauthenticated" }),
}));

vi.mock("../hooks/use-card-feedback", () => ({
  useCardFeedback: () => ({ vote: null, submitVote: vi.fn(), isPending: false }),
}));

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

// 5 cards so we can test the "within 3 of end" trigger without being at end immediately
const fiveCards: InsightCard[] = [
  ...mockCards,
  {
    id: "uuid-4",
    uploadId: null,
    headline: "Card Four Headline",
    keyMetric: "₴4,000",
    whyItMatters: "Reason four.",
    deepDive: "Deep four.",
    severity: "low",
    category: "shopping",
    createdAt: "2026-04-04T12:00:00.000000Z",
  },
  {
    id: "uuid-5",
    uploadId: null,
    headline: "Card Five Headline",
    keyMetric: "₴5,000",
    whyItMatters: "Reason five.",
    deepDive: "Deep five.",
    severity: "low",
    category: "other",
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

  it("Next button is disabled at last card when hasNextPage is false", () => {
    render(<CardStackNavigator cards={mockCards} hasNextPage={false} />);
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    expect(screen.getByRole("button", { name: /next insight/i })).toBeDisabled();
  });

  it("Next button is disabled at last card when no pagination props provided", () => {
    render(<CardStackNavigator cards={mockCards} />);
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    expect(screen.getByRole("button", { name: /next insight/i })).toBeDisabled();
  });

  it("Next button stays enabled at last card when hasNextPage=true", () => {
    render(<CardStackNavigator cards={mockCards} hasNextPage={true} />);
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    expect(screen.getByRole("button", { name: /next insight/i })).not.toBeDisabled();
  });

  it("progress counter shows 'X of Y' when hasNextPage is false", () => {
    render(<CardStackNavigator cards={mockCards} hasNextPage={false} />);
    expect(screen.getByText("1 of 3")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    expect(screen.getByText("2 of 3")).toBeInTheDocument();
  });

  it("progress counter shows 'X of Y+' suffix when hasNextPage=true", () => {
    render(<CardStackNavigator cards={mockCards} hasNextPage={true} />);
    expect(screen.getByText("1 of 3+")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    expect(screen.getByText("2 of 3+")).toBeInTheDocument();
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

  // Pagination: onLoadMore trigger tests (AC #1, #2)
  it("onLoadMore is called when navigating within 3 cards of end with hasNextPage=true", () => {
    const onLoadMore = vi.fn();
    // 5 cards: cards.length - 3 = 2. Trigger fires when currentIndex >= 2 (pre-increment).
    // Click 1: currentIndex=0 → 0>=2? No. Click 2: currentIndex=1 → 1>=2? No.
    // Click 3: currentIndex=2 → 2>=2? Yes → onLoadMore fires.
    render(
      <CardStackNavigator
        cards={fiveCards}
        hasNextPage={true}
        isFetchingNextPage={false}
        onLoadMore={onLoadMore}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /next insight/i })); // 0→1
    fireEvent.click(screen.getByRole("button", { name: /next insight/i })); // 1→2
    fireEvent.click(screen.getByRole("button", { name: /next insight/i })); // 2→3, trigger!
    expect(onLoadMore).toHaveBeenCalledTimes(1);
  });

  it("onLoadMore is NOT called when hasNextPage=false", () => {
    const onLoadMore = vi.fn();
    render(
      <CardStackNavigator
        cards={fiveCards}
        hasNextPage={false}
        isFetchingNextPage={false}
        onLoadMore={onLoadMore}
      />,
    );
    // Navigate past the trigger threshold (3 clicks)
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    expect(onLoadMore).not.toHaveBeenCalled();
  });

  it("onLoadMore is NOT called when isFetchingNextPage=true (debounce guard)", () => {
    const onLoadMore = vi.fn();
    render(
      <CardStackNavigator
        cards={fiveCards}
        hasNextPage={true}
        isFetchingNextPage={true}
        onLoadMore={onLoadMore}
      />,
    );
    // Navigate past the trigger threshold (3 clicks)
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    expect(onLoadMore).not.toHaveBeenCalled();
  });

  it("skeleton card renders when isFetchingNextPage=true and at last card", () => {
    render(
      <CardStackNavigator
        cards={mockCards}
        hasNextPage={true}
        isFetchingNextPage={true}
        onLoadMore={vi.fn()}
      />,
    );
    // Navigate to last card (index 2)
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    // The loading skeleton container renders with data-testid
    expect(screen.getByTestId("loading-more-skeleton")).toBeInTheDocument();
  });

  it("skeleton card does NOT render when not at last card", () => {
    render(
      <CardStackNavigator
        cards={mockCards}
        hasNextPage={true}
        isFetchingNextPage={true}
        onLoadMore={vi.fn()}
      />,
    );
    // At index 0, not at last card — no skeleton
    expect(screen.queryByTestId("loading-more-skeleton")).not.toBeInTheDocument();
  });

  it("Next button disabled only when at last card AND !hasNextPage", () => {
    render(
      <CardStackNavigator
        cards={mockCards}
        hasNextPage={false}
        isFetchingNextPage={false}
        onLoadMore={vi.fn()}
      />,
    );
    // Not at last card yet — enabled
    expect(screen.getByRole("button", { name: /next insight/i })).not.toBeDisabled();
    // Navigate to last
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    fireEvent.click(screen.getByRole("button", { name: /next insight/i }));
    // At last card, hasNextPage=false → disabled
    expect(screen.getByRole("button", { name: /next insight/i })).toBeDisabled();
  });
});
