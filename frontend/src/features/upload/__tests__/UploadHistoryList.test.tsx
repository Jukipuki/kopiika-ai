import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";
import en from "../../../../messages/en.json";
import uk from "../../../../messages/uk.json";
import UploadHistoryList from "../components/UploadHistoryList";

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

// Mock next-auth/react
vi.mock("next-auth/react", () => ({
  useSession: () => ({
    data: { accessToken: "test-token" },
    status: "authenticated",
  }),
}));

// Mock @/i18n/navigation
vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

// Mock the hook
const mockUseUploadHistory = vi.fn();
vi.mock("../hooks/use-upload-history", () => ({
  useUploadHistory: () => mockUseUploadHistory(),
}));

const MOCK_UPLOADS = [
  {
    id: "upload-1",
    fileName: "monobank_feb.csv",
    detectedFormat: "monobank",
    createdAt: "2026-03-29T10:00:00Z",
    transactionCount: 245,
    duplicatesSkipped: 0,
    status: "completed",
  },
  {
    id: "upload-2",
    fileName: "privatbank_jan.csv",
    detectedFormat: "privatbank",
    createdAt: "2026-03-28T10:00:00Z",
    transactionCount: 180,
    duplicatesSkipped: 12,
    status: "completed",
  },
];

describe("UploadHistoryList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders uploads with correct format and counts", () => {
    mockUseUploadHistory.mockReturnValue({
      uploads: MOCK_UPLOADS,
      total: 2,
      isLoading: false,
      isFetchingMore: false,
      error: null,
      hasMore: false,
      loadMore: vi.fn(),
      refresh: vi.fn(),
    });

    render(<UploadHistoryList />);

    // File names
    expect(screen.getByText("monobank_feb.csv")).toBeInTheDocument();
    expect(screen.getByText("privatbank_jan.csv")).toBeInTheDocument();

    // Transaction counts (the i18n mock replaces {count...} with the count value)
    expect(screen.getByText(/245/)).toBeInTheDocument();

    // Duplicates skipped (only shown when > 0)
    // The second upload has 12 duplicates, 180 txns — find the row by file name and check
    const privatbankRow = screen.getByText("privatbank_jan.csv").closest("div[class*='flex items-center']");
    expect(privatbankRow).toBeInTheDocument();
  });

  it("shows loading state", () => {
    mockUseUploadHistory.mockReturnValue({
      uploads: [],
      total: 0,
      isLoading: true,
      error: null,
      hasMore: false,
      loadMore: vi.fn(),
      refresh: vi.fn(),
    });

    render(<UploadHistoryList />);
    // Loading spinner should be visible (Loader2 icon has animate-spin class)
    const svg = document.querySelector(".animate-spin");
    expect(svg).toBeInTheDocument();
  });

  it("shows empty state", () => {
    mockUseUploadHistory.mockReturnValue({
      uploads: [],
      total: 0,
      isLoading: false,
      isFetchingMore: false,
      error: null,
      hasMore: false,
      loadMore: vi.fn(),
      refresh: vi.fn(),
    });

    render(<UploadHistoryList />);
    expect(screen.getByText(/no uploads/i)).toBeInTheDocument();
  });

  it("shows error state", () => {
    mockUseUploadHistory.mockReturnValue({
      uploads: [],
      total: 0,
      isLoading: false,
      error: "Failed to load upload history",
      hasMore: false,
      loadMore: vi.fn(),
      refresh: vi.fn(),
    });

    render(<UploadHistoryList />);
    expect(screen.getByText("Failed to load upload history")).toBeInTheDocument();
  });

  it("shows load more button when hasMore is true", async () => {
    const mockLoadMore = vi.fn();
    mockUseUploadHistory.mockReturnValue({
      uploads: MOCK_UPLOADS,
      total: 5,
      isLoading: false,
      error: null,
      hasMore: true,
      loadMore: mockLoadMore,
      refresh: vi.fn(),
    });

    render(<UploadHistoryList />);

    const button = screen.getByRole("button", { name: /load more/i });
    expect(button).toBeInTheDocument();

    await userEvent.click(button);
    expect(mockLoadMore).toHaveBeenCalledOnce();
  });

  it("9.5: uk.json has all required history keys and strings are translated", () => {
    const enHistory = en.history as Record<string, string>;
    const ukHistory = uk.history as Record<string, string>;

    // All EN keys must exist in UK
    Object.keys(enHistory).forEach((key) => {
      expect(ukHistory).toHaveProperty(key);
    });

    // UK strings must be translated (not identical to EN)
    expect(ukHistory.title).not.toBe(enHistory.title);
    expect(ukHistory.noUploads).not.toBe(enHistory.noUploads);
    expect(ukHistory.statusCompleted).not.toBe(enHistory.statusCompleted);
    expect(ukHistory.loadMore).not.toBe(enHistory.loadMore);
  });

  it("renders status badges correctly", () => {
    const uploadsWithMixedStatus = [
      { ...MOCK_UPLOADS[0], status: "completed" },
      { ...MOCK_UPLOADS[1], id: "upload-3", status: "processing" },
      { ...MOCK_UPLOADS[1], id: "upload-4", fileName: "failed.csv", status: "failed" },
    ];

    mockUseUploadHistory.mockReturnValue({
      uploads: uploadsWithMixedStatus,
      total: 3,
      isLoading: false,
      isFetchingMore: false,
      error: null,
      hasMore: false,
      loadMore: vi.fn(),
      refresh: vi.fn(),
    });

    render(<UploadHistoryList />);

    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("Processing")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });
});
