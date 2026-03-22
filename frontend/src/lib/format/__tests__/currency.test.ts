import { describe, it, expect } from "vitest";
import { formatCurrency } from "../currency";

describe("formatCurrency", () => {
  it("8.6a formats UAH with Ukrainian locale by default", () => {
    const result = formatCurrency(1234.56);
    // uk-UA formatting: 1 234,56 ₴ (with non-breaking space)
    expect(result).toContain("1");
    expect(result).toContain("234");
    expect(result).toContain("56");
    expect(result).toContain("₴");
  });

  it("8.6b formats UAH with English locale", () => {
    const result = formatCurrency(1234.56, "en");
    // en-US formatting: UAH 1,234.56
    expect(result).toContain("1,234.56");
  });

  it("8.6c handles zero", () => {
    const result = formatCurrency(0);
    expect(result).toContain("0");
    expect(result).toContain("00");
  });

  it("8.6d handles negative amounts", () => {
    const result = formatCurrency(-50.5);
    expect(result).toMatch(/-|−|\(/); // Negative sign (hyphen, minus, or parenthesis)
    expect(result).toContain("50");
  });

  it("8.6e falls back to uk locale for unknown locale", () => {
    const result = formatCurrency(100, "fr");
    // Should fall back to uk-UA
    expect(result).toContain("₴");
  });
});
