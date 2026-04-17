"use client";

import { useEffect, useState, type SyntheticEvent } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useIssueReport, type IssueCategory } from "../hooks/use-issue-report";

interface ReportIssueFormProps {
  cardId: string;
  onClose: () => void;
}

export function ReportIssueForm({ cardId, onClose }: ReportIssueFormProps) {
  const t = useTranslations("feed.reportIssue");
  const { submitReport, isPending, isAlreadyReported, confirmationShown } =
    useIssueReport(cardId);
  const [category, setCategory] = useState<IssueCategory | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [freeText, setFreeText] = useState("");

  useEffect(() => {
    if (!confirmationShown) return;
    const timer = setTimeout(onClose, 2000);
    return () => clearTimeout(timer);
  }, [confirmationShown, onClose]);

  const handleSubmit = () => {
    if (!category) return;
    submitReport({ issueCategory: category, freeText: freeText || undefined });
  };

  if (confirmationShown) {
    return (
      <p
        className="mt-2 py-2 text-sm text-muted-foreground"
        role="status"
        aria-live="polite"
      >
        {t("success")}
      </p>
    );
  }

  if (isAlreadyReported) {
    return (
      <div
        className="mt-2 flex items-center justify-between py-2"
        role="status"
        aria-live="polite"
      >
        <p className="text-sm text-muted-foreground">{t("alreadyReported")}</p>
        <Button variant="ghost" size="sm" onClick={onClose}>
          {t("cancel")}
        </Button>
      </div>
    );
  }

  const stopGesture = (e: SyntheticEvent) => e.stopPropagation();

  return (
    <div
      className="mt-2 rounded-md border bg-card p-3 space-y-3"
      onClick={stopGesture}
      onPointerDown={stopGesture}
      onTouchStart={stopGesture}
      role="dialog"
      aria-label={t("title")}
    >
      <label className="block text-sm font-medium" htmlFor="report-category">
        {t("category.label")}
      </label>
      <Select
        value={category}
        onValueChange={(v) => setCategory(v as IssueCategory)}
        items={[
          { value: "bug", label: t("category.bug") },
          { value: "incorrect_info", label: t("category.incorrectInfo") },
          { value: "confusing", label: t("category.confusing") },
          { value: "other", label: t("category.other") },
        ]}
      >
        <SelectTrigger id="report-category">
          <SelectValue placeholder={t("category.label")} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="bug">{t("category.bug")}</SelectItem>
          <SelectItem value="incorrect_info">
            {t("category.incorrectInfo")}
          </SelectItem>
          <SelectItem value="confusing">{t("category.confusing")}</SelectItem>
          <SelectItem value="other">{t("category.other")}</SelectItem>
        </SelectContent>
      </Select>

      {!detailsOpen ? (
        <button
          type="button"
          className="text-sm text-muted-foreground underline"
          onClick={() => setDetailsOpen(true)}
        >
          {t("freeText.toggle")}
        </button>
      ) : (
        <div>
          <label htmlFor="report-free-text" className="sr-only">
            {t("freeText.placeholder")}
          </label>
          <textarea
            id="report-free-text"
            className="w-full resize-none rounded border p-2 text-sm"
            rows={3}
            maxLength={500}
            placeholder={t("freeText.placeholder")}
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
          />
          <p className="text-right text-xs text-muted-foreground">
            {t("freeText.counter", { count: freeText.length })}
          </p>
        </div>
      )}

      <div className="flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onClose}>
          {t("cancel")}
        </Button>
        <Button
          size="sm"
          disabled={!category || isPending}
          onClick={handleSubmit}
        >
          {t("submit")}
        </Button>
      </div>
    </div>
  );
}
