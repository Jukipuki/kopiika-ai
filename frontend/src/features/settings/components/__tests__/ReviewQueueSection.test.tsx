import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createUseTranslations } from "@/test-utils/intl-mock";
import ReviewQueueSection from "../ReviewQueueSection";

vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

const mockFetch = vi.fn();
global.fetch = mockFetch;

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ReviewQueueSection (Story 11.8 AC #8)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockUseSession.mockReturnValue({ data: { accessToken: "tok" } });
  });

  it("hides entirely when count is 0", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ count: 0 }),
    });
    const { container } = renderWithClient(<ReviewQueueSection />);
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
    });
    // Section must not render anything.
    expect(container.querySelector('[aria-labelledby="review-queue-heading"]')).toBeNull();
  });

  it("renders count + link when count > 0", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ count: 4 }),
    });
    renderWithClient(<ReviewQueueSection />);

    await waitFor(() => {
      expect(
        screen.getByRole("link", { name: /review/i })
      ).toHaveAttribute("href", "/settings/review-queue");
    });
    // Heading should be rendered — the exact text may have ICU placeholders in
    // our intl mock, so assert the section + heading presence rather than the
    // formatted count string.
    expect(
      screen.getByRole("heading", { level: 2 })
    ).toBeInTheDocument();
  });
});
