import en from "../../messages/en.json";

function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce((o: unknown, k: string) => {
    if (o && typeof o === "object" && k in (o as Record<string, unknown>)) {
      return (o as Record<string, unknown>)[k];
    }
    return undefined;
  }, obj);
}

export function createUseTranslations() {
  return (namespace: string) => {
    const nsObj = getNestedValue(en as Record<string, unknown>, namespace);
    return (key: string, values?: Record<string, unknown>) => {
      let val = nsObj && typeof nsObj === "object"
        ? getNestedValue(nsObj as Record<string, unknown>, key)
        : undefined;
      if (val === undefined) return `${namespace}.${key}`;
      if (values && typeof val === "string") {
        Object.entries(values).forEach(([k, v]) => {
          val = (val as string).replace(
            new RegExp(`\\{${k}[^}]*\\}`, "g"),
            String(v)
          );
        });
      }
      return val as string;
    };
  };
}

export const mockNextIntl = {
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
  NextIntlClientProvider: ({ children }: { children: React.ReactNode }) => children,
};
