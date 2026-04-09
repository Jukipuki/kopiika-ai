"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { getZone, ZONE_FLAT_COLORS } from "../score-zones";
import type { HealthScoreHistoryItem } from "../types";

interface HealthScoreTrendProps {
  data: HealthScoreHistoryItem[];
  locale: string;
}

const PADDING = { top: 10, right: 10, bottom: 24, left: 32 };
const CHART_WIDTH = 300;
const CHART_HEIGHT = 120;
const TOOLTIP_WIDTH = 50;

function xScale(i: number, total: number): number {
  if (total <= 1) return PADDING.left;
  return PADDING.left + (i / (total - 1)) * (CHART_WIDTH - PADDING.left - PADDING.right);
}

function yScale(score: number): number {
  return CHART_HEIGHT - PADDING.bottom - (score / 100) * (CHART_HEIGHT - PADDING.top - PADDING.bottom);
}

function clampTooltipX(x: number): number {
  const half = TOOLTIP_WIDTH / 2;
  return Math.max(half, Math.min(x, CHART_WIDTH - half));
}

export function HealthScoreTrend({ data, locale }: HealthScoreTrendProps) {
  const t = useTranslations("profile.healthScore");
  const [tooltip, setTooltip] = useState<{ x: number; y: number; score: number; date: string } | null>(null);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(true);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mql.matches);
    const handler = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  if (data.length === 0) return null;

  if (data.length === 1) {
    return (
      <p className="text-center text-sm text-muted-foreground mt-4">
        {t("trendEmpty")}
      </p>
    );
  }

  const latestScore = data[data.length - 1].score;
  const zone = getZone(latestScore);
  const color = ZONE_FLAT_COLORS[zone];

  const dateFormatter = new Intl.DateTimeFormat(locale === "uk" ? "uk-UA" : "en-US", {
    month: "short",
    day: "numeric",
  });

  const points = data.map((d, i) => `${xScale(i, data.length)},${yScale(d.score)}`).join(" ");
  const areaPoints = `${points} ${xScale(data.length - 1, data.length)},${yScale(0)} ${xScale(0, data.length)},${yScale(0)}`;

  const ariaLabel = t("trendLabel") + ": " + data.map((d) => `${d.score} ${dateFormatter.format(new Date(d.calculatedAt))}`).join(", ");

  // Compute polyline total length for stroke-dasharray animation
  let totalLength = 0;
  for (let i = 1; i < data.length; i++) {
    const x0 = xScale(i - 1, data.length), y0 = yScale(data[i - 1].score);
    const x1 = xScale(i, data.length), y1 = yScale(data[i].score);
    totalLength += Math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2);
  }

  return (
    <div className="mt-4 relative" style={{ minHeight: 120 }}>
      <p className="text-sm font-medium text-muted-foreground mb-2">{t("trendTitle")}</p>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        width="100%"
        role="img"
        aria-label={ariaLabel}
        style={{ minHeight: 120 }}
      >
        {/* Y-axis labels */}
        {[0, 50, 100].map((v) => (
          <text
            key={v}
            x={PADDING.left - 4}
            y={yScale(v)}
            textAnchor="end"
            dominantBaseline="central"
            fontSize={7}
            className="fill-muted-foreground"
          >
            {v}
          </text>
        ))}

        {/* Grid lines */}
        {[0, 50, 100].map((v) => (
          <line
            key={`grid-${v}`}
            x1={PADDING.left}
            y1={yScale(v)}
            x2={CHART_WIDTH - PADDING.right}
            y2={yScale(v)}
            stroke="currentColor"
            className="text-muted/10"
            strokeWidth={0.5}
          />
        ))}

        {/* Area fill */}
        <polygon points={areaPoints} fill={color} opacity={0.1} />

        {/* Line */}
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth={2}
          strokeLinejoin="round"
          strokeDasharray={prefersReducedMotion ? undefined : totalLength}
          strokeDashoffset={prefersReducedMotion ? undefined : 0}
          style={
            prefersReducedMotion
              ? undefined
              : {
                  animation: `draw-line 0.8s ease-in-out`,
                }
          }
        />

        {/* Data points */}
        {data.map((d, i) => (
          <circle
            key={d.calculatedAt}
            cx={xScale(i, data.length)}
            cy={yScale(d.score)}
            r={3}
            fill={color}
            stroke="white"
            strokeWidth={1}
            className="cursor-pointer"
            onMouseEnter={() =>
              setTooltip({
                x: xScale(i, data.length),
                y: yScale(d.score),
                score: d.score,
                date: dateFormatter.format(new Date(d.calculatedAt)),
              })
            }
            onMouseLeave={() => setTooltip(null)}
            onTouchStart={() =>
              setTooltip({
                x: xScale(i, data.length),
                y: yScale(d.score),
                score: d.score,
                date: dateFormatter.format(new Date(d.calculatedAt)),
              })
            }
          />
        ))}

        {/* Tooltip */}
        {tooltip && (
          <g>
            <rect
              x={clampTooltipX(tooltip.x) - TOOLTIP_WIDTH / 2}
              y={tooltip.y - 22}
              width={TOOLTIP_WIDTH}
              height={16}
              rx={3}
              fill="black"
              opacity={0.8}
            />
            <text
              x={clampTooltipX(tooltip.x)}
              y={tooltip.y - 14}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={7}
              fill="white"
            >
              {tooltip.score} · {tooltip.date}
            </text>
          </g>
        )}

        {/* X-axis date labels (first and last) */}
        {[0, data.length - 1].map((i) => (
          <text
            key={`date-${i}`}
            x={xScale(i, data.length)}
            y={CHART_HEIGHT - 4}
            textAnchor={i === 0 ? "start" : "end"}
            fontSize={7}
            className="fill-muted-foreground"
          >
            {dateFormatter.format(new Date(data[i].calculatedAt))}
          </text>
        ))}
      </svg>

      {/* Keyframes for line draw animation */}
      {!prefersReducedMotion && (
        <style>{`
          @keyframes draw-line {
            from { stroke-dashoffset: ${totalLength}; }
            to { stroke-dashoffset: 0; }
          }
        `}</style>
      )}
    </div>
  );
}
