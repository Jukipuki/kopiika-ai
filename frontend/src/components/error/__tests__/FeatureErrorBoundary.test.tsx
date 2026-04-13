import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

// Track the retry callback so we can assert on it
let capturedRetry: (() => void) | undefined;

// Mock next/error - catchError returns a component that renders children,
// and when an error occurs, renders the fallback
vi.mock("next/error", () => ({
  unstable_catchError: (
    fallback: (
      props: { feature: string },
      errorInfo: { unstable_retry: () => void },
    ) => React.ReactNode,
  ) => {
    // Return a component that simulates error boundary behavior via a prop
    return function MockErrorBoundary({
      children,
      __simulateError,
      ...props
    }: {
      children?: React.ReactNode;
      __simulateError?: boolean;
      feature: string;
    }) {
      if (__simulateError) {
        const retry = vi.fn();
        capturedRetry = retry;
        return fallback(
          { feature: props.feature },
          { error: new Error("test error"), unstable_retry: retry },
        );
      }
      return children;
    };
  },
}));

// Import after mocks
import FeatureErrorBoundary from "../FeatureErrorBoundary";

describe("FeatureErrorBoundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedRetry = undefined;
  });

  it("renders children when no error", () => {
    render(
      <FeatureErrorBoundary feature="feed">
        <div>Feed content</div>
      </FeatureErrorBoundary>,
    );

    expect(screen.getByText("Feed content")).toBeInTheDocument();
  });

  it.each([
    ["feed", "Our AI tripped over your insights — give it another try?"],
    [
      "profile",
      "Your financial profile took an unexpected nap — let's wake it up!",
    ],
    [
      "upload",
      "The upload gremlins struck again — let's give it another shot!",
    ],
    [
      "settings",
      "Settings got a bit tangled — try again and we'll sort it out!",
    ],
  ] as const)(
    "renders correct i18n message for %s feature on error",
    (feature, expectedMessage) => {
      const BoundaryWithError = FeatureErrorBoundary as React.ComponentType<{
        feature: string;
        __simulateError?: boolean;
      }>;
      render(<BoundaryWithError feature={feature} __simulateError />);

      expect(screen.getByText(expectedMessage)).toBeInTheDocument();
    },
  );

  it("renders retry button on error", () => {
    const BoundaryWithError = FeatureErrorBoundary as React.ComponentType<{
      feature: string;
      __simulateError?: boolean;
    }>;
    render(<BoundaryWithError feature="feed" __simulateError />);

    expect(screen.getByText("Try again")).toBeInTheDocument();
  });

  it("calls retry when retry button is clicked", async () => {
    const user = userEvent.setup();
    const BoundaryWithError = FeatureErrorBoundary as React.ComponentType<{
      feature: string;
      __simulateError?: boolean;
    }>;
    render(<BoundaryWithError feature="feed" __simulateError />);

    await user.click(screen.getByText("Try again"));

    expect(capturedRetry).toHaveBeenCalled();
  });
});
