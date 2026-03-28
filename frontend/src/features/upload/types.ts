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

// SSE event types
export type JobStatus = "processing" | "completed" | "failed";

export interface PipelineProgressEvent {
  event: "pipeline-progress";
  jobId: string;
  step: string;
  progress: number;
  message: string;
}

export interface JobCompleteEvent {
  event: "job-complete";
  jobId: string;
  status: "completed";
  totalInsights: number;
}

export interface JobFailedEvent {
  event: "job-failed";
  jobId: string;
  status: "failed";
  error: { code: string; message: string };
}

export type SSEEvent = PipelineProgressEvent | JobCompleteEvent | JobFailedEvent;

export interface JobStatusState {
  status: JobStatus | "connecting" | "idle";
  step: string | null;
  progress: number;
  error: { code: string; message: string } | null;
  result: { totalInsights: number } | null;
  isConnected: boolean;
}
