"use client";

import { useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import type { UploadResponse, UploadError } from "../types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const ALLOWED_TYPES = ["text/csv", "application/pdf"];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

interface UseUploadReturn {
  upload: (file: File) => Promise<UploadResponse | null>;
  isUploading: boolean;
  error: UploadError | null;
  clearError: () => void;
  formatResult: UploadResponse | null;
}

export function useUpload(): UseUploadReturn {
  const { data: session } = useSession();
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<UploadError | null>(null);
  const [formatResult, setFormatResult] = useState<UploadResponse | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const upload = useCallback(
    async (file: File): Promise<UploadResponse | null> => {
      setError(null);
      setFormatResult(null);

      // Client-side validation
      if (!ALLOWED_TYPES.includes(file.type)) {
        setError({
          code: "INVALID_FILE_TYPE",
          message: "INVALID_FILE_TYPE",
          suggestions: ["Try exporting your bank statement as CSV."],
        });
        return null;
      }

      if (file.size > MAX_FILE_SIZE) {
        setError({
          code: "FILE_TOO_LARGE",
          message: "FILE_TOO_LARGE",
        });
        return null;
      }

      if (!session?.accessToken) {
        setError({
          code: "UNAUTHENTICATED",
          message: "UNAUTHENTICATED",
        });
        return null;
      }

      setIsUploading(true);

      try {
        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch(`${API_URL}/api/v1/uploads`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session.accessToken}`,
          },
          body: formData,
        });

        if (!res.ok) {
          const data = await res.json();
          const serverError = data.error || { code: "UPLOAD_FAILED", message: "UPLOAD_FAILED" };
          setError({
            code: serverError.code,
            message: serverError.message,
            details: serverError.details,
            suggestions: serverError.suggestions || [],
          });
          return null;
        }

        const data: UploadResponse = await res.json();
        setFormatResult(data);
        return data;
      } catch {
        setError({
          code: "UPLOAD_FAILED",
          message: "UPLOAD_FAILED",
        });
        return null;
      } finally {
        setIsUploading(false);
      }
    },
    [session?.accessToken],
  );

  return { upload, isUploading, error, clearError, formatResult };
}
