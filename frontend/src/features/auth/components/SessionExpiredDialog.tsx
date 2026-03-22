"use client";

interface SessionExpiredDialogProps {
  onLogin: () => void;
}

export default function SessionExpiredDialog({
  onLogin,
}: SessionExpiredDialogProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="session-expired-title"
    >
      <div className="mx-4 w-full max-w-sm rounded-2xl bg-background p-6 shadow-xl border border-foreground/10">
        <h2
          id="session-expired-title"
          className="text-lg font-semibold text-foreground text-center"
        >
          Session Expired
        </h2>
        <p className="mt-2 text-sm text-foreground/60 text-center">
          Your session has expired due to inactivity. Please log in again.
        </p>
        <div className="mt-6">
          <button
            onClick={onLogin}
            className="w-full rounded-lg bg-[#6C63FF] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#5B54E6] focus:outline-none focus:ring-2 focus:ring-[#6C63FF] focus:ring-offset-2 transition-colors"
          >
            Log in
          </button>
        </div>
      </div>
    </div>
  );
}
