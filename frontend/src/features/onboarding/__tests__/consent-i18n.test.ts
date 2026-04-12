import { describe, it, expect } from "vitest";
import en from "../../../../messages/en.json";
import uk from "../../../../messages/uk.json";

type Dict = Record<string, unknown>;

function get(obj: Dict, path: string): unknown {
  return path.split(".").reduce<unknown>((acc, key) => {
    if (acc && typeof acc === "object" && key in (acc as Dict)) {
      return (acc as Dict)[key];
    }
    return undefined;
  }, obj);
}

const REQUIRED_KEYS = [
  "onboarding.privacy.title",
  "onboarding.privacy.subtitle",
  "onboarding.privacy.dataCollected.title",
  "onboarding.privacy.dataCollected.body",
  "onboarding.privacy.aiProcessing.title",
  "onboarding.privacy.aiProcessing.body",
  "onboarding.privacy.storage.title",
  "onboarding.privacy.storage.body",
  "onboarding.privacy.access.title",
  "onboarding.privacy.access.body",
  "onboarding.privacy.consentLabel",
  "onboarding.privacy.continue",
  "onboarding.privacy.submitting",
  "onboarding.privacy.logOut",
];

describe("onboarding.privacy i18n keys", () => {
  for (const key of REQUIRED_KEYS) {
    it(`en.json defines ${key} as a non-empty string`, () => {
      const val = get(en as Dict, key);
      expect(typeof val).toBe("string");
      expect((val as string).length).toBeGreaterThan(0);
    });

    it(`uk.json defines ${key} as a non-empty string`, () => {
      const val = get(uk as Dict, key);
      expect(typeof val).toBe("string");
      expect((val as string).length).toBeGreaterThan(0);
    });
  }
});
