import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import en from "../../../../messages/en.json";
import uk from "../../../../messages/uk.json";

const FORBIDDEN_TERMS = [
  "guardrail",
  "grounding",
  "canary",
  "jailbreak",
  "prompt injection",
];

// Length budgets for tight slots (chip labels, send-button label) per
// AC #13. Numbers are conservative pre-fits — tests fail loud if a
// translator stretches a string past the slot, not on a render diff.
const CHARACTER_BUDGETS: Record<string, number> = {
  "composer.send": 18,
  "composer.send_aria": 32,
  "session.new": 22,
  "delete.session.menu_label": 18,
  "streaming.scroll_to_bottom": 22,
  "refusal.try_again": 22,
};

function flatten(obj: Record<string, unknown>, prefix = ""): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v)) {
      Object.assign(out, flatten(v as Record<string, unknown>, key));
    } else if (typeof v === "string") {
      out[key] = v;
    }
  }
  return out;
}

function walkSrc(dir: string, files: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === "__tests__") continue;
    const full = join(dir, entry);
    const s = statSync(full);
    if (s.isDirectory()) walkSrc(full, files);
    else if (/\.(ts|tsx)$/.test(entry)) files.push(full);
  }
  return files;
}

const enChat = flatten((en as { chat: Record<string, unknown> }).chat, "chat");
const ukChat = flatten((uk as { chat: Record<string, unknown> }).chat, "chat");

describe("chat i18n forbidden-terms lint", () => {
  for (const term of FORBIDDEN_TERMS) {
    it(`en.json contains no "${term}" inside chat.*`, () => {
      const matches = Object.entries(enChat).filter(([, v]) =>
        v.toLowerCase().includes(term),
      );
      expect(matches, `forbidden term in: ${matches.map(([k]) => k).join(", ")}`).toEqual([]);
    });
    it(`uk.json contains no "${term}" inside chat.*`, () => {
      const matches = Object.entries(ukChat).filter(([, v]) =>
        v.toLowerCase().includes(term),
      );
      expect(matches, `forbidden term in: ${matches.map(([k]) => k).join(", ")}`).toEqual([]);
    });
  }
});

describe("chat i18n character-budget assertions", () => {
  for (const [key, budget] of Object.entries(CHARACTER_BUDGETS)) {
    const fullKey = `chat.${key}`;
    it(`en chat.${key} ≤ ${budget} chars`, () => {
      const s = enChat[fullKey] ?? "";
      expect(s.length, `en chat.${key} = "${s}" (${s.length} chars)`).toBeLessThanOrEqual(budget);
    });
    it(`uk chat.${key} ≤ ${budget} chars`, () => {
      const s = ukChat[fullKey] ?? "";
      expect(s.length, `uk chat.${key} = "${s}" (${s.length} chars)`).toBeLessThanOrEqual(budget);
    });
  }
});

describe("chat i18n key parity", () => {
  it("en + uk chat.* have identical key sets", () => {
    const enKeys = new Set(Object.keys(enChat));
    const ukKeys = new Set(Object.keys(ukChat));
    const onlyEn = [...enKeys].filter((k) => !ukKeys.has(k));
    const onlyUk = [...ukKeys].filter((k) => !enKeys.has(k));
    expect(onlyEn, "missing in uk").toEqual([]);
    expect(onlyUk, "missing in en").toEqual([]);
  });
});

describe("chat i18n source-AST scan", () => {
  // Regex pre-pass: every `t('chat.<key>')` or `t('<key>')` referenced
  // inside features/chat resolves to a real entry under chat.* in both
  // locales. Per AC #13, runs as a static scan; not foolproof against
  // dynamically composed keys, but catches typos.
  const featureRoot = join(__dirname, "..");
  const allFiles = walkSrc(featureRoot);
  const tCallPattern = /\bt\(\s*["'`]([\w.]+)["'`]/g;

  it("every t('<key>') call resolves in en.json", () => {
    const referenced = new Set<string>();
    for (const file of allFiles) {
      const src = readFileSync(file, "utf8");
      // Skip i18n.test.ts (this file) — no useful t() calls anyway.
      if (file.endsWith("i18n.test.ts")) continue;
      let m: RegExpExecArray | null;
      while ((m = tCallPattern.exec(src))) referenced.add(m[1]);
    }
    const missing: string[] = [];
    for (const key of referenced) {
      // Translation files use chat.* prefix; component calls use bare keys
      // because useTranslations("chat") scopes them. So look up both paths.
      if (enChat[`chat.${key}`] !== undefined) continue;
      if (enChat[key] !== undefined) continue;
      // Heuristic: refusalCopyKey() returns `refusal.<reason>.copy` — the
      // 6 reasons are dynamically composed; assert each separately.
      if (/^refusal\.\w+\.copy$/.test(key)) continue;
      // streaming.thinking_<toolName> dynamically composed for known tools.
      if (/^streaming\.thinking_/.test(key)) continue;
      // citations.category.<code> + citations.profile_field.<field> dynamic.
      if (/^citations\.(category|profile_field)\./.test(key)) continue;
      missing.push(key);
    }
    expect(missing).toEqual([]);
  });

  it("all 6 refusal reasons have copy keys in both locales", () => {
    const reasons = [
      "guardrail_blocked",
      "ungrounded",
      "rate_limited",
      "prompt_leak_detected",
      "tool_blocked",
      "transient_error",
    ];
    for (const r of reasons) {
      expect(enChat[`chat.refusal.${r}.copy`]).toBeTruthy();
      expect(ukChat[`chat.refusal.${r}.copy`]).toBeTruthy();
    }
  });
});
