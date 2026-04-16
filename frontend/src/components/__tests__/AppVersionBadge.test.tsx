import { render, screen } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

import AppVersionBadge from "../AppVersionBadge";

describe("AppVersionBadge", () => {
  const ORIGINAL_VERSION = process.env.NEXT_PUBLIC_APP_VERSION;

  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_APP_VERSION", "9.9.9");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    if (ORIGINAL_VERSION !== undefined) {
      process.env.NEXT_PUBLIC_APP_VERSION = ORIGINAL_VERSION;
    } else {
      delete process.env.NEXT_PUBLIC_APP_VERSION;
    }
  });

  it("renders the injected NEXT_PUBLIC_APP_VERSION prefixed with 'v'", () => {
    render(<AppVersionBadge />);
    expect(screen.getByText("v9.9.9")).toBeInTheDocument();
  });

  it("merges a custom className with the default styling", () => {
    render(<AppVersionBadge className="custom-placement" />);
    const badge = screen.getByText("v9.9.9");
    // Override is applied
    expect(badge.className).toContain("custom-placement");
    // Default typography is preserved — callers extend, not replace.
    expect(badge.className).toContain("text-xs");
    expect(badge.className).toContain("pointer-events-none");
  });
});
