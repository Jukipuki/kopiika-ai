import { cn } from "@/lib/utils";

type AppVersionBadgeProps = {
  className?: string;
};

export default function AppVersionBadge({ className }: AppVersionBadgeProps) {
  const version = process.env.NEXT_PUBLIC_APP_VERSION ?? "0.0.0+dev";
  return (
    <span
      className={cn(
        "fixed bottom-2 left-2 z-40 text-xs text-foreground/40 select-none pointer-events-none",
        className,
      )}
      aria-label={`Application version ${version}`}
    >
      v{version}
    </span>
  );
}
