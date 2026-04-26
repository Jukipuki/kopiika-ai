"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useChatSession } from "../hooks/useChatSession";
import { SessionRow } from "./SessionRow";
import { DeleteAllDialog } from "./DeleteAllDialog";
import { ConcurrentSessionsDialog } from "./ConcurrentSessionsDialog";

const BULK_DELETE = process.env.NEXT_PUBLIC_CHAT_BULK_DELETE === "true";
const DELETE_UNDO = process.env.NEXT_PUBLIC_CHAT_DELETE_UNDO === "true";

export function SessionList() {
  const t = useTranslations("chat");
  const {
    sessions,
    activeSessionId,
    selectSession,
    createSession,
    isCreating,
    createError,
    deleteSession,
    isDeleting,
  } = useChatSession();
  const [deleteAllOpen, setDeleteAllOpen] = useState(false);
  const [concurrentOpen, setConcurrentOpen] = useState(false);

  const onNew = async () => {
    try {
      await createSession();
    } catch (e) {
      const err = e as { status?: number; bodyText?: string };
      if (err.status === 429 || (err.bodyText && err.bodyText.includes("CHAT_RATE_LIMITED"))) {
        setConcurrentOpen(true);
        return;
      }
      toast.error(t("session.create_error"));
    }
  };

  const onDelete = async (id: string) => {
    try {
      await deleteSession(id);
      toast.success(t("delete.session.toast"), {
        action: DELETE_UNDO
          ? { label: t("delete.session.undo"), onClick: () => {/* 10.10 owns */} }
          : undefined,
      });
    } catch {
      toast.error(t("delete.session.error"));
    }
  };

  return (
    <aside aria-label={t("a11y.session_list_label")} className="flex h-full w-full flex-col border-r border-border/60 sm:w-64">
      <div className="border-b border-border/60 p-3">
        <Button onClick={onNew} disabled={isCreating} className="w-full justify-start gap-2">
          <Plus aria-hidden="true" className="h-4 w-4" />
          {t("session.new")}
        </Button>
        {createError && createError.status !== 429 && (
          <p className="mt-2 text-xs text-destructive">{t("session.create_error")}</p>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {sessions.length === 0 ? (
          <p className="px-2 py-4 text-center text-xs text-muted-foreground">
            {t("session.empty_list")}
          </p>
        ) : (
          <ul className="space-y-1">
            {sessions.map((s) => (
              <li key={s.sessionId}>
                <SessionRow
                  session={s}
                  active={s.sessionId === activeSessionId}
                  onSelect={() => selectSession(s.sessionId)}
                  onDelete={() => onDelete(s.sessionId)}
                  isDeleting={isDeleting}
                />
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="border-t border-border/60 p-3">
        <button
          type="button"
          onClick={() => setDeleteAllOpen(true)}
          aria-disabled={!BULK_DELETE}
          title={!BULK_DELETE ? t("delete.all.coming_soon") : undefined}
          className="text-xs text-destructive underline disabled:opacity-50"
        >
          {t("delete.all.link")}
        </button>
      </div>
      <DeleteAllDialog
        open={deleteAllOpen}
        onOpenChange={setDeleteAllOpen}
        bulkAvailable={BULK_DELETE}
        onConfirm={() => setDeleteAllOpen(false)}
      />
      <ConcurrentSessionsDialog
        open={concurrentOpen}
        onOpenChange={setConcurrentOpen}
        sessions={sessions}
        onPickSession={(id) => {
          selectSession(id);
          setConcurrentOpen(false);
        }}
      />
    </aside>
  );
}
