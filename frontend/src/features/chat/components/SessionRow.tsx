"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { MoreHorizontal } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import type { ChatSession } from "../lib/chat-types";
import { DeleteSessionDialog } from "./DeleteSessionDialog";

interface Props {
  session: ChatSession;
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
  isDeleting: boolean;
}

export function SessionRow({ session, active, onSelect, onDelete, isDeleting }: Props) {
  const t = useTranslations("chat");
  const [confirmOpen, setConfirmOpen] = useState(false);

  return (
    <div
      className={cn(
        "group flex items-center gap-1 rounded px-2 py-1.5",
        active ? "bg-muted" : "hover:bg-muted/50",
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        className="flex-1 truncate text-left text-sm focus-visible:outline-2 focus-visible:outline-ring"
      >
        {session.title || t("session.untitled")}
      </button>
      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label={t("delete.session.kebab_label")}
          className="rounded p-1 hover:bg-muted/80 focus-visible:outline-2 focus-visible:outline-ring"
        >
          <MoreHorizontal aria-hidden="true" className="h-4 w-4" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            variant="destructive"
            onSelect={() => setConfirmOpen(true)}
          >
            {t("delete.session.menu_label")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <DeleteSessionDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        onConfirm={() => {
          setConfirmOpen(false);
          onDelete();
        }}
        isDeleting={isDeleting}
      />
    </div>
  );
}
