"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { getZone, ZONE_GRADIENT_COLORS } from "../score-zones";
import type { HealthScoreBreakdown } from "../types";

interface HealthScoreRingProps {
  score: number;
  breakdown: HealthScoreBreakdown;
}

const BREAKDOWN_KEYS = [
  "savings_ratio",
  "category_diversity",
  "expense_regularity",
  "income_coverage",
] as const;

export function HealthScoreRing({ score, breakdown }: HealthScoreRingProps) {
  const t = useTranslations("profile.healthScore");
  const [showBreakdown, setShowBreakdown] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(true);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") {
      return;
    }
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mql.matches);
    const handler = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  const zone = getZone(score);
  const colors = ZONE_GRADIENT_COLORS[zone];

  const size = 160;
  const strokeWidth = 12;
  const center = size / 2;
  const radius = center - strokeWidth;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const gradientId = "healthScoreGradient";

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative">
        <svg
          width={size}
          height={size}
          role="img"
          aria-label={t("ariaLabel", { score })}
        >
          <defs>
            <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={colors.start} />
              <stop offset="100%" stopColor={colors.end} />
            </linearGradient>
          </defs>
          {/* Background ring */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            stroke="currentColor"
            className="text-muted/20"
            strokeWidth={strokeWidth}
            fill="none"
          />
          {/* Score ring */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            stroke={`url(#${gradientId})`}
            strokeWidth={strokeWidth}
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{
              transition: prefersReducedMotion
                ? "none"
                : "stroke-dashoffset 1s ease-in-out",
            }}
            transform={`rotate(-90 ${center} ${center})`}
          />
          {/* Center score text */}
          <text
            x={center}
            y={center - 8}
            textAnchor="middle"
            dominantBaseline="central"
            className="fill-foreground font-bold"
            style={{ fontSize: "2rem" }}
          >
            {score}
          </text>
          {/* Zone label */}
          <text
            x={center}
            y={center + 18}
            textAnchor="middle"
            dominantBaseline="central"
            className="fill-muted-foreground"
            style={{ fontSize: "0.7rem" }}
          >
            {t(`zone.${zone}`)}
          </text>
        </svg>
      </div>

      {/* Breakdown toggle */}
      <button
        type="button"
        onClick={() => setShowBreakdown(!showBreakdown)}
        className="text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        {showBreakdown ? t("hideBreakdown") : t("showBreakdown")}
      </button>

      {/* Breakdown details */}
      {showBreakdown && (
        <div className="w-full max-w-xs space-y-2">
          {BREAKDOWN_KEYS.map((key) => (
            <div key={key} className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                {t(`breakdown.${key}`)}
              </span>
              <span className="font-medium">{breakdown[key]}/100</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
