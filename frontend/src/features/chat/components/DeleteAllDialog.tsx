"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  bulkAvailable: boolean;
}

export function DeleteAllDialog({ open, onOpenChange, onConfirm, bulkAvailable }: Props) {
  const t = useTranslations("chat");
  const matchString = t("delete.all.confirm_input_match");
  const [input, setInput] = useState("");
  const matches = input.trim().toLowerCase() === matchString.toLowerCase();

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) setInput(""); onOpenChange(o); }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("delete.all.confirm_title")}</AlertDialogTitle>
          <AlertDialogDescription>{t("delete.all.confirm_body")}</AlertDialogDescription>
        </AlertDialogHeader>
        {!bulkAvailable ? (
          <p className="rounded bg-muted p-3 text-sm text-muted-foreground">
            {t("delete.all.coming_soon")}
          </p>
        ) : (
          <label className="block text-sm">
            <span className="block text-muted-foreground">
              {t("delete.all.confirm_input_label", { match: matchString })}
            </span>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="mt-1 w-full rounded border border-input bg-background px-2 py-1.5 text-sm focus:outline-2 focus:outline-ring"
              autoComplete="off"
            />
          </label>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel autoFocus>{t("delete.all.cancel")}</AlertDialogCancel>
          {bulkAvailable && (
            <AlertDialogAction
              variant="destructive"
              onClick={onConfirm}
              disabled={!matches}
            >
              {t("delete.all.confirm_cta")}
            </AlertDialogAction>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
