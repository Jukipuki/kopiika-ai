import type {
  CitationDto,
  CategoryCitation,
  ProfileFieldCitation,
  TransactionCitation,
  RagDocCitation,
} from "./chat-types";

// Per 10.6b AC #2 + 10.7 AC #8 label rules:
// - transaction.label / rag_doc.label render verbatim (server-emitted, may
//   contain user/data content).
// - category.label / profile_field.label are server canonical English; the
//   FE localizes via `chat.citations.{category,profile_field}.<key>` keys
//   (closes TD-124). Fall back to server label if a key is missing.

type Translator = (key: string, values?: Record<string, unknown>) => string;
type Locale = "uk" | "en";

const monthNamesEn = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];
const monthNamesUk = [
  "Січень",
  "Лютий",
  "Березень",
  "Квітень",
  "Травень",
  "Червень",
  "Липень",
  "Серпень",
  "Вересень",
  "Жовтень",
  "Листопад",
  "Грудень",
];

function formatMonthYear(asOf: string | null | undefined, locale: Locale): string {
  if (!asOf) return "";
  const d = new Date(asOf);
  if (isNaN(d.getTime())) return asOf;
  const months = locale === "uk" ? monthNamesUk : monthNamesEn;
  return `${months[d.getMonth()]} ${d.getFullYear()}`;
}

/** True if the key resolves to a real translation (next-intl returns the
 *  key itself when missing). */
function tryTranslate(t: Translator, key: string, values?: Record<string, unknown>): string | null {
  let s: string;
  try {
    s = t(key, values);
  } catch {
    return null;
  }
  if (!s || s === key || s.endsWith(`.${key.split(".").pop()}`)) return null;
  return s;
}

export function renderCategoryLabel(c: CategoryCitation, t: Translator): string {
  const localized = tryTranslate(t, `citations.category.${c.code}`);
  return localized ?? c.label;
}

export function renderProfileFieldLabel(c: ProfileFieldCitation, t: Translator, locale: Locale): string {
  const month = formatMonthYear(c.asOf, locale);
  const localized = tryTranslate(t, `citations.profile_field.${c.field}`, { month });
  return localized ?? c.label;
}

export function renderTransactionLabel(c: TransactionCitation): string {
  return c.label;
}

export function renderRagDocLabel(c: RagDocCitation): string {
  return c.label;
}

export function renderCitationLabel(c: CitationDto, t: Translator, locale: Locale): string {
  switch (c.kind) {
    case "transaction":
      return renderTransactionLabel(c);
    case "rag_doc":
      return renderRagDocLabel(c);
    case "category":
      return renderCategoryLabel(c, t);
    case "profile_field":
      return renderProfileFieldLabel(c, t, locale);
  }
}
