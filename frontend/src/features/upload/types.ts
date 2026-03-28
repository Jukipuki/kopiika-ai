export type UploadState = "idle" | "drag-over" | "selected" | "uploading" | "error";

export interface UploadResponse {
  jobId: string;
  statusUrl: string;
  detectedFormat: string | null;
  encoding: string | null;
  columnCount: number | null;
}

export interface UploadError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  suggestions?: string[];
}
