import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";

let mockSearchParams = new URLSearchParams();

vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

vi.mock("@/i18n/navigation", async () => {
  const React = await import("react");
  return {
    Link: ({
      href,
      children,
      ...props
    }: {
      href: string;
      children: React.ReactNode;
    } & Record<string, unknown>) =>
      React.createElement("a", { href, ...props }, children),
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => mockSearchParams,
}));

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: null, status: "unauthenticated" }),
  signIn: vi.fn(),
}));

import LoginPage from "@/app/[locale]/(auth)/login/page";

describe("LoginPage success banner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows success banner when ?reset=success query param is present", () => {
    mockSearchParams = new URLSearchParams({ reset: "success" });
    render(<LoginPage />);

    expect(
      screen.getByText(/password updated — please log in/i)
    ).toBeInTheDocument();
  });

  it("does not show banner when ?reset=success is absent", () => {
    mockSearchParams = new URLSearchParams();
    render(<LoginPage />);

    expect(
      screen.queryByText(/password updated — please log in/i)
    ).not.toBeInTheDocument();
  });
});
