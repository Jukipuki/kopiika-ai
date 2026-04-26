"use client";

import { useTranslations } from "next-intl";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import type { ChatSession } from "../lib/chat-types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sessions: ChatSession[];
  onPickSession: (id: string) => void;
}

export function ConcurrentSessionsDialog({ open, onOpenChange, sessions, onPickSession }: Props) {
  const t = useTranslations("chat");
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("ratelimit.concurrent_sessions_title")}</AlertDialogTitle>
          <AlertDialogDescription>
            {t("ratelimit.concurrent_sessions_body")}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <ul className="max-h-60 overflow-y-auto divide-y divide-border/60 rounded border">
          {sessions.map((s) => (
            <li key={s.sessionId}>
              <button
                type="button"
                onClick={() => onPickSession(s.sessionId)}
                className="block w-full px-3 py-2 text-left text-sm hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
              >
                {s.title || t("session.untitled")}
              </button>
            </li>
          ))}
        </ul>
        <AlertDialogFooter>
          <AlertDialogCancel autoFocus>{t("delete.session.cancel")}</AlertDialogCancel>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
