export type ScoreZone = "needsAttention" | "developing" | "healthy" | "excellent";

export function getZone(score: number): ScoreZone {
  if (score <= 30) return "needsAttention";
  if (score <= 60) return "developing";
  if (score <= 80) return "healthy";
  return "excellent";
}

/** Gradient pairs used by the ring component. */
export const ZONE_GRADIENT_COLORS: Record<ScoreZone, { start: string; end: string }> = {
  needsAttention: { start: "#F87171", end: "#EF4444" },
  developing: { start: "#FBBF24", end: "#F59E0B" },
  healthy: { start: "#8B5CF6", end: "#7C3AED" },
  excellent: { start: "#2DD4BF", end: "#14B8A6" },
};

/** Flat colors used by the trend chart (matches gradient end colors). */
export const ZONE_FLAT_COLORS: Record<ScoreZone, string> = {
  needsAttention: "#EF4444",
  developing: "#F59E0B",
  healthy: "#7C3AED",
  excellent: "#14B8A6",
};
