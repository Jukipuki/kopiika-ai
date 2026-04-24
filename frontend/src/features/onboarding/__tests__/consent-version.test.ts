import { describe, expect, it } from "vitest";

import {
  CONSENT_TYPE_AI_PROCESSING,
  CONSENT_TYPE_CHAT_PROCESSING,
  CURRENT_CHAT_CONSENT_VERSION,
  CURRENT_CONSENT_VERSION,
} from "../consent-version";

const VERSION_FORMAT = /^\d{4}-\d{2}-\d{2}-v\d+$/;

describe("consent-version constants", () => {
  it("exports CURRENT_CONSENT_VERSION as a non-empty YYYY-MM-DD-vN string", () => {
    expect(CURRENT_CONSENT_VERSION).toMatch(VERSION_FORMAT);
  });

  it("exports CURRENT_CHAT_CONSENT_VERSION as a non-empty YYYY-MM-DD-vN string", () => {
    expect(CURRENT_CHAT_CONSENT_VERSION).toMatch(VERSION_FORMAT);
  });

  it("exports CONSENT_TYPE_AI_PROCESSING as 'ai_processing'", () => {
    expect(CONSENT_TYPE_AI_PROCESSING).toBe("ai_processing");
  });

  it("exports CONSENT_TYPE_CHAT_PROCESSING as 'chat_processing'", () => {
    expect(CONSENT_TYPE_CHAT_PROCESSING).toBe("chat_processing");
  });

  it("treats the two version streams as independent identifiers", () => {
    // They can happen to be equal in practice, but they are logically
    // independent — the app reads each one separately to gate its own
    // consent surface.
    expect(CURRENT_CONSENT_VERSION).not.toBe(CONSENT_TYPE_AI_PROCESSING);
    expect(CURRENT_CHAT_CONSENT_VERSION).not.toBe(
      CONSENT_TYPE_CHAT_PROCESSING,
    );
  });
});
