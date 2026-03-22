const localeMap: Record<string, string> = {
  uk: "uk-UA",
  en: "en-US",
};

export function formatCurrency(
  amount: number,
  locale: string = "uk"
): string {
  const intlLocale = localeMap[locale] || localeMap.uk;

  return new Intl.NumberFormat(intlLocale, {
    style: "currency",
    currency: "UAH",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}
