const localeMap: Record<string, string> = {
  uk: "uk-UA",
  en: "en-US",
};

export function formatDate(
  date: Date | string | number,
  locale: string = "uk",
  options?: Intl.DateTimeFormatOptions
): string {
  const intlLocale = localeMap[locale] || localeMap.uk;
  const dateObj = date instanceof Date ? date : new Date(date);

  return new Intl.DateTimeFormat(intlLocale, options).format(dateObj);
}

export function formatDateTime(
  date: Date | string | number,
  locale: string = "uk"
): string {
  return formatDate(date, locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateLong(
  date: Date | string | number,
  locale: string = "uk"
): string {
  return formatDate(date, locale, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}
