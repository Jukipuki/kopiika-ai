"use client";

import type { SeverityLevel } from "../types";

const SEVERITY_CONFIG = {
  high: {
    label: "High Priority",
    icon: "🔴",
    className: "bg-red-100 text-red-800",
    ariaLabel: "High priority insight",
  },
  medium: {
    label: "Medium",
    icon: "🟡",
    className: "bg-yellow-100 text-yellow-800",
    ariaLabel: "Medium priority insight",
  },
  low: {
    label: "Low",
    icon: "🟢",
    className: "bg-green-100 text-green-800",
    ariaLabel: "Low priority insight",
  },
} as const;

interface TriageBadgeProps {
  severity: SeverityLevel;
}

export function TriageBadge({ severity }: TriageBadgeProps) {
  const config = SEVERITY_CONFIG[severity];

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${config.className}`}
      aria-label={config.ariaLabel}
    >
      <span aria-hidden="true">{config.icon}</span>
      {config.label}
    </span>
  );
}
