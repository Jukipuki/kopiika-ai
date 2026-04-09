export function formatCurrency(kopiykas: number, locale: string): string {
  return new Intl.NumberFormat(locale === "uk" ? "uk-UA" : "en-US", {
    style: "currency",
    currency: "UAH",
  }).format(kopiykas / 100);
}
