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

export interface DateRange {
  start: string;
  end: string;
}

export interface JobCompleteEvent {
  event: "job-complete";
  jobId: string;
  status: "completed";
  totalInsights: number;
  duplicatesSkipped?: number;
  newTransactions?: number;
  bankName?: string | null;
  transactionCount?: number;
  dateRange?: DateRange | null;
}

export interface JobFailedEvent {
  event: "job-failed";
  jobId: string;
  status: "failed";
  error: { code: string; message: string };
  isRetryable?: boolean;
}

export interface JobRetryingEvent {
  event: "job-retrying";
  jobId: string;
  retryCount: number;
  maxRetries: number;
}

export interface JobResumedEvent {
  event: "job-resumed";
  jobId: string;
  resumeFromStep: string | null;
}

export type SSEEvent = PipelineProgressEvent | JobCompleteEvent | JobFailedEvent | JobRetryingEvent | JobResumedEvent;

export interface JobStatusResult {
  totalInsights: number;
  duplicatesSkipped?: number;
  newTransactions?: number;
  bankName?: string | null;
  transactionCount?: number;
  dateRange?: DateRange | null;
}

export interface JobStatusState {
  status: JobStatus | "retrying" | "connecting" | "idle";
  step: string | null;
  progress: number;
  message: string | null;
  error: { code: string; message: string } | null;
  result: JobStatusResult | null;
  isConnected: boolean;
  isRetryable: boolean;
  retryCount: number;
}
