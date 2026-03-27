export type UploadState = "idle" | "drag-over" | "selected" | "uploading" | "error";

export interface UploadResponse {
  jobId: string;
  statusUrl: string;
}

export interface UploadError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}
