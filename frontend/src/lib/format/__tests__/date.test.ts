import { describe, it, expect } from "vitest";
import { formatDate, formatDateTime, formatDateLong } from "../date";

// Use a fixed date to ensure deterministic results
const testDate = new Date("2025-03-15T14:30:00Z");

describe("formatDate", () => {
  it("8.7a formats date with Ukrainian locale by default", () => {
    const result = formatDate(testDate);
    // uk-UA short format uses dot separators (e.g., 15.03.2025)
    expect(result).toMatch(/\./);
    expect(result).toContain("2025");
  });

  it("8.7b formats date with English locale", () => {
    const result = formatDate(testDate, "en");
    // en-US short format uses slashes (e.g., 3/15/2025)
    expect(result).toMatch(/\//);
    expect(result).toContain("2025");
  });

  it("8.7c accepts custom options", () => {
    const result = formatDate(testDate, "en", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
    expect(result).toContain("March");
    expect(result).toContain("15");
    expect(result).toContain("2025");
  });

  it("8.7d accepts string date input", () => {
    const result = formatDate("2025-03-15T14:30:00Z");
    expect(result).toContain("2025");
  });

  it("8.7e accepts timestamp number input", () => {
    const result = formatDate(testDate.getTime());
    expect(result).toContain("2025");
  });

  it("8.7f falls back to uk locale for unknown locale", () => {
    const result = formatDate(testDate, "fr");
    // Should fall back to uk-UA
    expect(result).toContain("2025");
  });
});

describe("formatDateTime", () => {
  it("8.7g formats date and time with Ukrainian locale", () => {
    const result = formatDateTime(testDate);
    // Should include both date and time (colon separator for HH:MM)
    expect(result).toContain("2025");
    expect(result).toMatch(/\d{2}:\d{2}/);
  });

  it("8.7h formats date and time with English locale", () => {
    const result = formatDateTime(testDate, "en");
    expect(result).toContain("2025");
    expect(result).toMatch(/\d{1,2}:\d{2}/);
  });
});

describe("formatDateLong", () => {
  it("8.7i formats long date with Ukrainian locale", () => {
    const result = formatDateLong(testDate);
    // uk-UA long format includes Ukrainian month name (not English)
    expect(result).toContain("2025");
    expect(result).not.toMatch(/March/i);
  });

  it("8.7j formats long date with English locale", () => {
    const result = formatDateLong(testDate, "en");
    expect(result).toContain("March");
    expect(result).toContain("15");
    expect(result).toContain("2025");
  });
});
