"use client";

import { AlertTriangle, AlertCircle, Info, type LucideIcon } from "lucide-react";
import type { SeverityLevel } from "../types";

interface SeverityConfig {
  label: string;
  Icon: LucideIcon;
  className: string;
  ariaLabel: string;
}

const SEVERITY_CONFIG: Record<SeverityLevel, SeverityConfig> = {
  critical: {
    label: "Critical",
    Icon: AlertTriangle,
    className: "bg-red-100 text-red-800",
    ariaLabel: "Severity: Critical",
  },
  warning: {
    label: "Warning",
    Icon: AlertCircle,
    className: "bg-amber-100 text-amber-800",
    ariaLabel: "Severity: Warning",
  },
  info: {
    label: "Info",
    // Visual "Info" vs aria-label "Informational" is intentional per AC #5 — do not align.
    Icon: Info,
    className: "bg-teal-100 text-teal-800",
    ariaLabel: "Severity: Informational",
  },
  high: {
    label: "Critical",
    Icon: AlertTriangle,
    className: "bg-red-100 text-red-800",
    ariaLabel: "Severity: Critical",
  },
  medium: {
    label: "Warning",
    Icon: AlertCircle,
    className: "bg-amber-100 text-amber-800",
    ariaLabel: "Severity: Warning",
  },
  low: {
    label: "Info",
    Icon: Info,
    className: "bg-teal-100 text-teal-800",
    ariaLabel: "Severity: Informational",
  },
};

interface TriageBadgeProps {
  severity: SeverityLevel;
}

export function TriageBadge({ severity }: TriageBadgeProps) {
  const config = SEVERITY_CONFIG[severity];
  const { Icon } = config;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${config.className}`}
      aria-label={config.ariaLabel}
    >
      <Icon size={12} aria-hidden="true" />
      {config.label}
    </span>
  );
}
