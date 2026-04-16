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

  // Story 2.9: Multi-currency support
  describe("multi-currency (Story 2.9)", () => {
    it("formats CHF using Swiss franc output", () => {
      const result = formatCurrency(100, "uk", "CHF");
      expect(result).toContain("100");
      expect(result).toContain("CHF");
    });

    it("formats JPY using Yen symbol", () => {
      const result = formatCurrency(100, "en", "JPY");
      expect(result).toContain("100");
      // Intl output for JPY can be "¥100.00" or "JPY 100.00" depending on ICU version.
      expect(result).toMatch(/¥|JPY/);
    });

    it("formats CZK", () => {
      const result = formatCurrency(100, "uk", "CZK");
      expect(result).toContain("100");
      expect(result).toMatch(/Kč|CZK/);
    });

    it("formats TRY", () => {
      const result = formatCurrency(100, "en", "TRY");
      expect(result).toContain("100");
      expect(result).toMatch(/₺|TRY/);
    });

    it("no currency arg defaults to UAH (backward compat)", () => {
      const result = formatCurrency(100, "uk");
      expect(result).toContain("₴");
    });

    it("unknown currency falls back to UAH to avoid throwing", () => {
      const result = formatCurrency(100, "uk", "XYZ");
      expect(result).toContain("₴");
    });

    it("currency code is case-insensitive", () => {
      const upper = formatCurrency(100, "en", "USD");
      const lower = formatCurrency(100, "en", "usd");
      expect(lower).toBe(upper);
    });
  });
});
