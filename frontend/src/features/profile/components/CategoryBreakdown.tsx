"use client";

import { useTranslations, useLocale } from "next-intl";
import { formatCurrency, useCategoryLabel } from "../format";
import type { CategoryBreakdown as CategoryBreakdownData } from "../types";

interface CategoryBreakdownProps {
  data: CategoryBreakdownData;
}

const CATEGORY_COLORS = [
  "#2563eb", // blue-600
  "#dc2626", // red-600
  "#16a34a", // green-600
  "#ca8a04", // yellow-600
  "#9333ea", // purple-600
  "#0891b2", // cyan-600
  "#ea580c", // orange-600
  "#db2777", // pink-600
  "#4f46e5", // indigo-600
  "#65a30d", // lime-600
];

export function CategoryBreakdown({ data }: CategoryBreakdownProps) {
  const t = useTranslations("profile.categoryBreakdown");
  const locale = useLocale();
  const categoryLabel = useCategoryLabel();

  const { categories, totalExpenses } = data;

  const ariaLabel = categories
    .map((c) => `${categoryLabel(c.category)} ${c.percentage}%`)
    .join(", ");

  // SVG donut chart parameters
  const strokeWidth = 32;
  const center = 100; // half of viewBox 200
  const radius = center - strokeWidth / 2;
  const circumference = 2 * Math.PI * radius;

  // Calculate segment offsets
  let cumulativePercent = 0;
  const segments = categories.map((cat, i) => {
    const segmentLength = (cat.percentage / 100) * circumference;
    const rotation = (cumulativePercent / 100) * 360 - 90;
    cumulativePercent += cat.percentage;
    return {
      ...cat,
      color: CATEGORY_COLORS[i % CATEGORY_COLORS.length],
      dashArray: `${segmentLength} ${circumference - segmentLength}`,
      rotation,
    };
  });

  return (
    <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6">
      {/* Donut Chart — 160px mobile, 200px desktop via responsive classes */}
      <div className="shrink-0 w-40 h-40 sm:w-[200px] sm:h-[200px]">
        <svg
          viewBox="0 0 200 200"
          className="w-full h-full"
          role="img"
          aria-label={t("ariaLabel") + ": " + ariaLabel}
        >
          <title>{t("title")}</title>
          <desc>{t("ariaLabel") + ": " + ariaLabel}</desc>
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
          {/* Category segments */}
          {segments.map((seg) => (
            <circle
              key={seg.category}
              cx={center}
              cy={center}
              r={radius}
              stroke={seg.color}
              strokeWidth={strokeWidth}
              fill="none"
              strokeDasharray={seg.dashArray}
              transform={`rotate(${seg.rotation} ${center} ${center})`}
            />
          ))}
          {/* Center total */}
          <text
            x={center}
            y={center}
            textAnchor="middle"
            dominantBaseline="central"
            className="fill-foreground font-bold text-sm"
          >
            {formatCurrency(totalExpenses, locale)}
          </text>
        </svg>
      </div>

      {/* Legend */}
      <div className="w-full space-y-2">
        {segments.map((seg) => (
          <div
            key={seg.category}
            className="flex items-center gap-2 text-sm"
          >
            <span
              className="inline-block h-3 w-3 shrink-0 rounded-sm"
              style={{ backgroundColor: seg.color }}
              aria-hidden="true"
            />
            <span className="truncate flex-1">
              {categoryLabel(seg.category)}
            </span>
            <span className="font-medium whitespace-nowrap">
              {formatCurrency(seg.amount, locale)}
            </span>
            <span className="text-muted-foreground whitespace-nowrap">
              {t("percentOfTotal", { percent: seg.percentage })}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
