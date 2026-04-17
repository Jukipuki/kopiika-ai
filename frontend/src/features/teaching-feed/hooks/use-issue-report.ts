"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type IssueCategory = "bug" | "incorrect_info" | "confusing" | "other";

interface SubmitReportInput {
  issueCategory: IssueCategory;
  freeText?: string;
}

export function useIssueReport(cardId: string) {
  const { data: session } = useSession();
  const [isAlreadyReported, setIsAlreadyReported] = useState(false);
  const [confirmationShown, setConfirmationShown] = useState(false);

  const mutation = useMutation({
    mutationFn: async ({ issueCategory, freeText }: SubmitReportInput) => {
      const res = await fetch(
        `${API_URL}/api/v1/feedback/cards/${cardId}/report`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session?.accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            issueCategory,
            freeText: freeText || null,
          }),
        },
      );
      if (res.status === 409) {
        setIsAlreadyReported(true);
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setConfirmationShown(true);
    },
  });

  return {
    submitReport: mutation.mutate,
    isPending: mutation.isPending,
    isAlreadyReported,
    confirmationShown,
  };
}
