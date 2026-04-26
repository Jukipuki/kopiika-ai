import { render } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import axe from "axe-core";
import { createUseTranslations } from "@/test-utils/intl-mock";
import { Composer } from "../components/Composer";
import { RefusalBubble } from "../components/RefusalBubble";
import type { ChatTurnState } from "../hooks/useChatStream";

vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: () => ({
      matches: false,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  });
}

async function runAxe(node: Element): Promise<axe.Result[]> {
  const results = await axe.run(node, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] },
  });
  return results.violations;
}

describe("axe-core smoke (WCAG 2.1 AA)", () => {
  it("Composer has no AA violations", async () => {
    const { container } = render(<Composer onSend={() => undefined} disabled={false} />);
    const violations = await runAxe(container);
    expect(
      violations.map((v) => `${v.id}: ${v.help}`),
      `axe found violations`,
    ).toEqual([]);
  });

  it("RefusalBubble (rate_limited) has no AA violations", async () => {
    const turn: ChatTurnState = {
      id: "rl-axe",
      role: "assistant",
      text: "",
      createdAt: "2026-04-26T10:00:00Z",
      refusal: {
        reason: "rate_limited",
        correlationId: "deadbeef-1234-5678-9012-345678901234",
        retryAfterSeconds: 60,
      },
    };
    const { container } = render(<RefusalBubble turn={turn} />);
    const violations = await runAxe(container);
    expect(
      violations.map((v) => `${v.id}: ${v.help}`),
      `axe found violations`,
    ).toEqual([]);
  });
});
