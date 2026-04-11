import { useTranslations } from "next-intl";

export function formatCurrency(kopiykas: number, locale: string): string {
  return new Intl.NumberFormat(locale === "uk" ? "uk-UA" : "en-US", {
    style: "currency",
    currency: "UAH",
  }).format(kopiykas / 100);
}

// Canonical category slugs that have explicit translations in
// messages/*.json under `profile.categories`. Must stay in sync.
const KNOWN_CATEGORIES = new Set([
  "groceries",
  "restaurants",
  "transport",
  "entertainment",
  "utilities",
  "healthcare",
  "shopping",
  "travel",
  "education",
  "finance",
  "subscriptions",
  "fuel",
  "atm_cash",
  "government",
  "other",
  "uncategorized",
]);

// Convert an unknown slug like "dining_out" into a readable "Dining Out".
function humanizeCategorySlug(slug: string): string {
  return slug
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/**
 * Hook returning a function that maps a backend category slug to a
 * user-facing label. Known slugs resolve through i18n; unknown slugs
 * fall back to a humanized form ("dining_out" → "Dining Out").
 */
export function useCategoryLabel(): (slug: string) => string {
  const t = useTranslations("profile.categories");
  return (slug: string) =>
    KNOWN_CATEGORIES.has(slug) ? t(slug) : humanizeCategorySlug(slug);
}
