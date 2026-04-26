import { describe, it, expect, vi } from "vitest";
import {
  renderCitationLabel,
  renderCategoryLabel,
  renderProfileFieldLabel,
} from "../lib/citation-label";
import type {
  CategoryCitation,
  ProfileFieldCitation,
  TransactionCitation,
  RagDocCitation,
} from "../lib/chat-types";

function tFactory(map: Record<string, string>) {
  return vi.fn((key: string, values?: Record<string, unknown>) => {
    let v = map[key];
    if (v == null) return key;
    if (values) {
      for (const [k, val] of Object.entries(values)) {
        v = v.replace(new RegExp(`\\{${k}\\}`, "g"), String(val));
      }
    }
    return v;
  });
}

describe("renderCategoryLabel", () => {
  it("uses localized key when present", () => {
    const c: CategoryCitation = { kind: "category", code: "groceries", label: "Groceries" };
    const t = tFactory({ "citations.category.groceries": "Продукти" });
    expect(renderCategoryLabel(c, t)).toBe("Продукти");
  });

  it("falls back to server label when key missing", () => {
    const c: CategoryCitation = { kind: "category", code: "weird", label: "Server-only" };
    const t = tFactory({});
    expect(renderCategoryLabel(c, t)).toBe("Server-only");
  });
});

describe("renderProfileFieldLabel", () => {
  it("interpolates month/year for the active locale (UA)", () => {
    const c: ProfileFieldCitation = {
      kind: "profile_field",
      field: "monthly_expenses_kopiykas",
      value: 4530000,
      currency: "UAH",
      asOf: "2026-04-01",
      label: "Monthly expenses (Apr 2026)",
    };
    const t = tFactory({
      "citations.profile_field.monthly_expenses_kopiykas": "Місячні витрати ({month})",
    });
    expect(renderProfileFieldLabel(c, t, "uk")).toBe("Місячні витрати (Квітень 2026)");
  });

  it("interpolates EN month name", () => {
    const c: ProfileFieldCitation = {
      kind: "profile_field",
      field: "monthly_expenses_kopiykas",
      value: 4530000,
      currency: "UAH",
      asOf: "2026-05-01",
      label: "Monthly expenses",
    };
    const t = tFactory({
      "citations.profile_field.monthly_expenses_kopiykas": "Monthly expenses ({month})",
    });
    expect(renderProfileFieldLabel(c, t, "en")).toBe("Monthly expenses (May 2026)");
  });

  it("falls back to server label when key missing", () => {
    const c: ProfileFieldCitation = {
      kind: "profile_field",
      field: "obscure_field",
      value: 0,
      asOf: "2026-04-01",
      label: "Server says hi",
    };
    const t = tFactory({});
    expect(renderProfileFieldLabel(c, t, "en")).toBe("Server says hi");
  });
});

describe("renderCitationLabel verbatim cases", () => {
  it("transaction.label renders verbatim regardless of t()", () => {
    const c: TransactionCitation = {
      kind: "transaction",
      id: "id-1",
      bookedAt: "2026-03-14",
      description: "Coffee",
      amountKopiykas: -8500,
      currency: "UAH",
      categoryCode: "dining",
      label: "Coffee · 2026-03-14",
    };
    const t = tFactory({});
    expect(renderCitationLabel(c, t, "en")).toBe("Coffee · 2026-03-14");
  });

  it("rag_doc.label renders verbatim", () => {
    const c: RagDocCitation = {
      kind: "rag_doc",
      sourceId: "en/emergency-fund",
      title: "en/emergency-fund",
      snippet: "An emergency fund …",
      similarity: 0.83,
      label: "en/emergency-fund",
    };
    const t = tFactory({});
    expect(renderCitationLabel(c, t, "en")).toBe("en/emergency-fund");
  });
});
