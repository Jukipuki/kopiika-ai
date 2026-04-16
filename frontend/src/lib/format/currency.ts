const localeMap: Record<string, string> = {
  uk: "uk-UA",
  en: "en-US",
};

const SUPPORTED_CURRENCIES = new Set([
  "UAH",
  "USD",
  "EUR",
  "GBP",
  "PLN",
  "CHF",
  "JPY",
  "CZK",
  "TRY",
]);

export function formatCurrency(
  amount: number,
  locale: string = "uk",
  currency: string = "UAH",
): string {
  const intlLocale = localeMap[locale] || localeMap.uk;
  const normalizedCurrency = currency.toUpperCase();
  const safeCurrency = SUPPORTED_CURRENCIES.has(normalizedCurrency)
    ? normalizedCurrency
    : "UAH";

  return new Intl.NumberFormat(intlLocale, {
    style: "currency",
    currency: safeCurrency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}
