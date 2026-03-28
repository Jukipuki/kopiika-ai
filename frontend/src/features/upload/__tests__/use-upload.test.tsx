import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useUpload } from "../hooks/use-upload";

// Mock next-auth/react
const mockUseSession = vi.fn();
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
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

describe("useUpload", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSession.mockReturnValue({
      data: { accessToken: "test-token" },
      status: "authenticated",
    });
  });

  it("returns initial state", () => {
    const { result } = renderHook(() => useUpload());

    expect(result.current.isUploading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(typeof result.current.upload).toBe("function");
    expect(typeof result.current.clearError).toBe("function");
  });

  it("uploads file successfully and returns response", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ jobId: "job-123", statusUrl: "/api/v1/jobs/job-123" }),
    });

    const { result } = renderHook(() => useUpload());
    const file = createFile("statement.csv", 1024, "text/csv");

    let uploadResult: unknown;
    await act(async () => {
      uploadResult = await result.current.upload(file);
    });

    expect(uploadResult).toEqual({
      jobId: "job-123",
      statusUrl: "/api/v1/jobs/job-123",
    });
    expect(result.current.error).toBeNull();
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

  it("rejects invalid file type without calling API", async () => {
    const { result } = renderHook(() => useUpload());
    const file = createFile("image.png", 1024, "image/png");

    let uploadResult: unknown;
    await act(async () => {
      uploadResult = await result.current.upload(file);
    });

    expect(uploadResult).toBeNull();
    expect(result.current.error).toEqual(
      expect.objectContaining({ code: "INVALID_FILE_TYPE" }),
    );
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("rejects file exceeding 10MB without calling API", async () => {
    const { result } = renderHook(() => useUpload());
    const file = createFile("big.csv", 11 * 1024 * 1024, "text/csv");

    let uploadResult: unknown;
    await act(async () => {
      uploadResult = await result.current.upload(file);
    });

    expect(uploadResult).toBeNull();
    expect(result.current.error).toEqual(
      expect.objectContaining({ code: "FILE_TOO_LARGE" }),
    );
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("handles rate limit error from server", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      json: () =>
        Promise.resolve({
          error: { code: "RATE_LIMITED", message: "Rate limited" },
        }),
    });

    const { result } = renderHook(() => useUpload());
    const file = createFile("statement.csv", 1024, "text/csv");

    let uploadResult: unknown;
    await act(async () => {
      uploadResult = await result.current.upload(file);
    });

    expect(uploadResult).toBeNull();
    expect(result.current.error).toEqual(
      expect.objectContaining({ code: "RATE_LIMITED" }),
    );
  });

  it("handles network failure gracefully", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useUpload());
    const file = createFile("statement.csv", 1024, "text/csv");

    let uploadResult: unknown;
    await act(async () => {
      uploadResult = await result.current.upload(file);
    });

    expect(uploadResult).toBeNull();
    expect(result.current.error).toEqual(
      expect.objectContaining({ code: "UPLOAD_FAILED" }),
    );
  });

  it("returns UNAUTHENTICATED error when no session token", async () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: "unauthenticated",
    });

    const { result } = renderHook(() => useUpload());
    const file = createFile("statement.csv", 1024, "text/csv");

    let uploadResult: unknown;
    await act(async () => {
      uploadResult = await result.current.upload(file);
    });

    expect(uploadResult).toBeNull();
    expect(result.current.error).toEqual(
      expect.objectContaining({ code: "UNAUTHENTICATED" }),
    );
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("clears error with clearError", async () => {
    const { result } = renderHook(() => useUpload());
    const file = createFile("image.png", 1024, "image/png");

    await act(async () => {
      await result.current.upload(file);
    });

    expect(result.current.error).not.toBeNull();

    act(() => {
      result.current.clearError();
    });

    expect(result.current.error).toBeNull();
  });

  it("returns formatResult after successful upload with format detection", async () => {
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

    const { result } = renderHook(() => useUpload());
    const file = createFile("statement.csv", 1024, "text/csv");

    await act(async () => {
      await result.current.upload(file);
    });

    expect(result.current.formatResult).toEqual(
      expect.objectContaining({
        detectedFormat: "monobank",
        encoding: "windows-1251",
        columnCount: 10,
      }),
    );
  });

  it("parses suggestions from server error response", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      json: () =>
        Promise.resolve({
          error: {
            code: "UNSUPPORTED_BANK_FORMAT",
            message: "Unsupported",
            suggestions: ["Try Monobank CSV", "Other banks coming soon"],
          },
        }),
    });

    const { result } = renderHook(() => useUpload());
    const file = createFile("statement.csv", 1024, "text/csv");

    await act(async () => {
      await result.current.upload(file);
    });

    expect(result.current.error).toEqual(
      expect.objectContaining({
        code: "UNSUPPORTED_BANK_FORMAT",
        suggestions: ["Try Monobank CSV", "Other banks coming soon"],
      }),
    );
  });

  it("includes suggestions for client-side invalid file type", async () => {
    const { result } = renderHook(() => useUpload());
    const file = createFile("image.jpg", 1024, "image/jpeg");

    await act(async () => {
      await result.current.upload(file);
    });

    expect(result.current.error).toEqual(
      expect.objectContaining({
        code: "INVALID_FILE_TYPE",
        suggestions: ["Try exporting your bank statement as CSV."],
      }),
    );
  });

  it("sets isUploading during API call", async () => {
    let resolveUpload: (value: unknown) => void;
    mockFetch.mockReturnValue(
      new Promise((resolve) => {
        resolveUpload = resolve;
      }),
    );

    const { result } = renderHook(() => useUpload());
    const file = createFile("statement.csv", 1024, "text/csv");

    // Start upload (don't await)
    let uploadPromise: Promise<unknown>;
    act(() => {
      uploadPromise = result.current.upload(file);
    });

    // Should be uploading
    await waitFor(() => {
      expect(result.current.isUploading).toBe(true);
    });

    // Resolve the fetch
    await act(async () => {
      resolveUpload!({
        ok: true,
        json: () => Promise.resolve({ jobId: "job-1", statusUrl: "/api/v1/jobs/job-1" }),
      });
      await uploadPromise;
    });

    expect(result.current.isUploading).toBe(false);
  });
});
