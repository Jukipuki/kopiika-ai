"use client";

import { useTranslations, useLocale } from "next-intl";
import { signOut } from "next-auth/react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useAccountDeletion } from "../hooks/use-account-deletion";

export default function DataDeletion() {
  const t = useTranslations("settings.deleteData");
  const locale = useLocale();
  const { deleteAccount, isDeleting } = useAccountDeletion();

  const handleConfirmDelete = async () => {
    const success = await deleteAccount();
    if (success) {
      toast.success(t("success"));
      await signOut({ callbackUrl: `/${locale}/login` });
    } else {
      toast.error(t("error"));
    }
  };

  return (
    <section aria-labelledby="delete-data-heading">
      <Card className="border-destructive/50">
        <CardHeader>
          <h2
            id="delete-data-heading"
            className="text-lg font-medium leading-snug text-destructive"
          >
            {t("title")}
          </h2>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{t("description")}</p>
          <AlertDialog>
            <AlertDialogTrigger
              render={
                <Button
                  variant="destructive"
                  className="min-h-[44px] min-w-[44px]"
                  disabled={isDeleting}
                />
              }
            >
              {t("button")}
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{t("dialogTitle")}</AlertDialogTitle>
                <AlertDialogDescription>
                  {t("dialogDescription")}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleConfirmDelete}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  disabled={isDeleting}
                >
                  {isDeleting ? t("deleting") : t("confirm")}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </CardContent>
      </Card>
    </section>
  );
}
