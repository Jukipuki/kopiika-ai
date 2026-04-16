import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";
import UploadDropzone from "../components/UploadDropzone";

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

// Mock next-auth/react
const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

// Mock @/i18n/navigation — hoisted spy so tests can assert no auto-redirect (Story 2.8 AC #1)
const mockRouterPush = vi.fn();
vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
  useRouter: () => ({ push: mockRouterPush }),
}));

// Mock sonner
const mockToastSuccess = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => mockToastSuccess(...args),
    error: vi.fn(),
  },
}));

// Mock useJobStatus hook (overridable per-test via mockImplementation)
type MockJobStatusReturn = {
  status: "idle" | "connecting" | "processing" | "retrying" | "completed" | "failed";
  step: string | null;
  progress: number;
  message: string | null;
  error: { code: string; message: string } | null;
  result: Record<string, unknown> | null;
  isConnected: boolean;
  isRetryable: boolean;
  retryCount: number;
  retry: () => void;
};
const mockUseJobStatus = vi.fn<() => MockJobStatusReturn>(() => ({
  status: "idle",
  step: null,
  progress: 0,
  message: null,
  error: null,
  result: null,
  isConnected: false,
  isRetryable: true,
  retryCount: 0,
  retry: vi.fn(),
}));
vi.mock("../hooks/use-job-status", () => ({
  useJobStatus: (...args: unknown[]) => mockUseJobStatus(...(args as [])),
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

function createFile(
  name: string,
  size: number,
  type: string,
): File {
  const content = new Uint8Array(size);
  return new File([content], name, { type });
}

describe("UploadDropzone", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSession.mockReturnValue({
      data: { accessToken: "test-token" },
      status: "authenticated",
    });
    mockUseJobStatus.mockReturnValue({
      status: "idle",
      step: null,
      progress: 0,
      message: null,
      error: null,
      result: null,
      isConnected: false,
      isRetryable: true,
      retryCount: 0,
      retry: vi.fn(),
    });
  });

  it("renders idle state with drop text and file picker", () => {
    render(<UploadDropzone />);

    expect(
      screen.getByText("Drop your bank statement here"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("or click to select a file"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Upload bank statement file" }),
    ).toBeInTheDocument();
  });

  it("renders supported format guide", () => {
    render(<UploadDropzone />);

    expect(screen.getByText("Monobank CSV")).toBeInTheDocument();
  });

  it("renders trust message", () => {
    render(<UploadDropzone />);

    expect(
      screen.getByText("Your data stays encrypted and private"),
    ).toBeInTheDocument();
  });

  it("shows drag-over visual feedback", () => {
    render(<UploadDropzone />);

    const dropzone = screen.getByRole("button", {
      name: "Upload bank statement file",
    });

    fireEvent.dragEnter(dropzone, {
      dataTransfer: { files: [] },
    });

    // The dropzone should have the drag-over styling class
    expect(dropzone.className).toContain("border-primary");
  });

  it("accepts CSV file via file input and calls upload API", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ jobId: "job-123", statusUrl: "/api/v1/jobs/job-123" }),
    });

    render(<UploadDropzone />);

    const file = createFile("statement.csv", 1024, "text/csv");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/uploads"),
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            Authorization: "Bearer test-token",
          }),
        }),
      );
    });
  });

  it("shows error for invalid file type", async () => {
    render(<UploadDropzone />);

    const file = createFile("image.png", 1024, "image/png");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    // Use fireEvent to bypass accept attribute filtering
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(
        screen.getByText(
          "Only CSV and PDF files are supported.",
        ),
      ).toBeInTheDocument();
    });

    // Should NOT call the API
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("shows error for file too large", async () => {
    render(<UploadDropzone />);

    const file = createFile("big.csv", 11 * 1024 * 1024, "text/csv");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(
        screen.getByText(
          "This file is too large. Please upload files under 10MB.",
        ),
      ).toBeInTheDocument();
    });

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("shows upload progress indicator during upload", async () => {
    // Make fetch hang to keep uploading state
    mockFetch.mockReturnValue(new Promise(() => {}));

    render(<UploadDropzone />);

    const file = createFile("statement.csv", 1024, "text/csv");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(
        screen.getByText("Analyzing your transactions..."),
      ).toBeInTheDocument();
    });
  });

  it("shows rate limit error from server", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      json: () =>
        Promise.resolve({
          error: { code: "RATE_LIMITED", message: "Rate limited" },
        }),
    });

    render(<UploadDropzone />);

    const file = createFile("statement.csv", 1024, "text/csv");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(
        screen.getByText(
          "You've uploaded a lot of files recently. Please try again in a few minutes.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("shows try again button on error and can retry", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      json: () =>
        Promise.resolve({
          error: { code: "UPLOAD_FAILED", message: "Failed" },
        }),
    });

    render(<UploadDropzone />);

    const file = createFile("statement.csv", 1024, "text/csv");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(screen.getByText("Try again")).toBeInTheDocument();
    });

    // Click try again to clear error
    const user = userEvent.setup();
    await user.click(screen.getByText("Try again"));

    // Error should be cleared, back to idle
    expect(
      screen.getByText("Drop your bank statement here"),
    ).toBeInTheDocument();
  });

  it("is keyboard navigable", () => {
    render(<UploadDropzone />);

    const dropzone = screen.getByRole("button", {
      name: "Upload bank statement file",
    });
    expect(dropzone).toHaveAttribute("tabindex", "0");
  });

  it("transitions to processing state after successful upload", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ jobId: "job-123", statusUrl: "/api/v1/jobs/job-123" }),
    });

    render(<UploadDropzone />);

    const file = createFile("statement.csv", 1024, "text/csv");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await userEvent.upload(input, file);

    // After upload succeeds, component should have called upload and set jobId
    // The SSE hook (mocked as idle) will take over from here
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });
  });

  // ==================== Story 2.2: Error Suggestions & Format Detection ====================

  it("displays error suggestions from server", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      json: () =>
        Promise.resolve({
          error: {
            code: "UNSUPPORTED_BANK_FORMAT",
            message: "Unsupported bank format",
            suggestions: [
              "We currently support Monobank CSV",
              "Try uploading a Monobank statement",
            ],
          },
        }),
    });

    render(<UploadDropzone />);

    const file = createFile("statement.csv", 1024, "text/csv");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(
        screen.getByText("We couldn't recognize this bank statement format."),
      ).toBeInTheDocument();
    });

    // Suggestions should be rendered
    expect(
      screen.getByText("We currently support Monobank CSV"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Try uploading a Monobank statement"),
    ).toBeInTheDocument();
  });

  it("calls upload API and stores jobId after successful upload", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          jobId: "job-456",
          statusUrl: "/api/v1/jobs/job-456",
          detectedFormat: "monobank",
          encoding: "windows-1251",
          columnCount: 10,
        }),
    });

    render(<UploadDropzone />);

    const file = createFile("statement.csv", 1024, "text/csv");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(1);
      // Upload was made to the correct endpoint
      expect(mockFetch.mock.calls[0][0]).toContain("/api/v1/uploads");
    });
  });

  it("displays unsupported bank format error with suggestions", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      json: () =>
        Promise.resolve({
          error: {
            code: "INVALID_FILE_STRUCTURE",
            message: "Invalid structure",
            suggestions: [
              "Check that the file is a .csv with transaction data",
              "Try re-exporting from your bank app",
            ],
          },
        }),
    });

    render(<UploadDropzone />);

    const file = createFile("data.csv", 1024, "text/csv");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(
        screen.getByText("This file doesn't look like a bank statement."),
      ).toBeInTheDocument();
    });

    // Suggestion list should be visible
    const suggestions = screen.getByRole("list", { name: "Suggestions" });
    expect(suggestions).toBeInTheDocument();
    expect(suggestions.querySelectorAll("li")).toHaveLength(2);
  });

  // ==================== Story 2.8: Upload Completion UX & Summary ====================

  it("does not auto-redirect to /feed after a successful upload (Story 2.8)", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          jobId: "job-789",
          statusUrl: "/api/v1/jobs/job-789",
          detectedFormat: "monobank",
        }),
    });

    render(<UploadDropzone />);

    const file = createFile("statement.csv", 1024, "text/csv");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await userEvent.upload(input, file);

    // After upload, the user stays on the upload page (no navigation).
    // The mocked useJobStatus stays "idle", so we land in the "selected" branch:
    // the selected file name is visible and the upload dropzone has not been replaced.
    await waitFor(() => {
      expect(screen.getByText("statement.csv")).toBeInTheDocument();
    });
    // Primary regression guard: router.push must NEVER be called for the
    // pre-2.8 auto-redirect to `/feed?jobId=...`. Hoisted spy makes this
    // assertable across renders.
    expect(mockRouterPush).not.toHaveBeenCalled();
    expect(window.location.pathname).not.toContain("/feed");
    // The summary card (which would imply completion + the new flow) MUST NOT render
    expect(screen.queryByText("Your statement is ready")).not.toBeInTheDocument();
  });

  it("renders UploadSummaryCard with View Insights when job completes (Story 2.8)", () => {
    mockUseJobStatus.mockReturnValue({
      status: "completed",
      step: null,
      progress: 100,
      message: null,
      error: null,
      result: {
        totalInsights: 12,
        bankName: "Monobank",
        transactionCount: 245,
        dateRange: { start: "2026-02-01", end: "2026-02-28" },
        duplicatesSkipped: 3,
        newTransactions: 245,
      },
      isConnected: false,
      isRetryable: false,
      retryCount: 0,
      retry: vi.fn(),
    });

    render(<UploadDropzone />);

    expect(screen.getByText("Your statement is ready")).toBeInTheDocument();
    expect(screen.getByText("Monobank statement detected")).toBeInTheDocument();

    const viewInsights = screen.getByRole("link", { name: /View Insights/i });
    expect(viewInsights).toHaveAttribute("href", "/feed");

    // The legacy "File uploaded successfully!" copy should NOT render
    expect(
      screen.queryByText("File uploaded successfully!"),
    ).not.toBeInTheDocument();
  });

  it("does NOT render the summary card when job has failed (Story 2.8 AC #6)", () => {
    mockUseJobStatus.mockReturnValue({
      status: "failed",
      step: null,
      progress: 0,
      message: null,
      error: { code: "LLM_ERROR", message: "Something failed" },
      result: null,
      isConnected: false,
      isRetryable: true,
      retryCount: 0,
      retry: vi.fn(),
    });

    render(<UploadDropzone />);

    expect(screen.queryByText("Your statement is ready")).not.toBeInTheDocument();
    expect(
      screen.getByText("We couldn't process this file. Please try again."),
    ).toBeInTheDocument();
  });

  it("shows invalid file type error with suggestion", async () => {
    render(<UploadDropzone />);

    const file = createFile("spreadsheet.xlsx", 1024, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(
        screen.getByText("Only CSV and PDF files are supported."),
      ).toBeInTheDocument();
    });

    // Suggestion from client-side validation
    expect(
      screen.getByText("Try exporting your bank statement as CSV."),
    ).toBeInTheDocument();
  });
});
