import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

// Track router calls
const mockReplace = vi.fn();
let mockLocale = "uk";

// Mock next-intl
vi.mock("next-intl", () => ({
  useLocale: () => mockLocale,
}));

// Mock @/i18n/navigation
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => "/login",
}));

// Mock @/i18n/routing
vi.mock("@/i18n/routing", () => ({
  routing: {
    locales: ["uk", "en"],
    defaultLocale: "uk",
  },
}));

import AuthLayout from "../layout";

describe("AuthLayout locale toggle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLocale = "uk";
  });

  it("8.5 renders UA | EN toggle with UA highlighted when locale is uk", () => {
    render(
      <AuthLayout>
        <div>Test Content</div>
      </AuthLayout>
    );

    expect(screen.getByText("UA")).toBeInTheDocument();
    expect(screen.getByText("EN")).toBeInTheDocument();
    // UA should be highlighted (font-semibold)
    expect(screen.getByText("UA").className).toContain("font-semibold");
  });

  it("8.5b clicking toggle switches to next locale", async () => {
    const user = userEvent.setup();
    render(
      <AuthLayout>
        <div>Test Content</div>
      </AuthLayout>
    );

    const button = screen.getByRole("button", {
      name: /switch language/i,
    });
    await user.click(button);

    expect(mockReplace).toHaveBeenCalledWith("/login", { locale: "en" });
  });

  it("renders children inside layout", () => {
    render(
      <AuthLayout>
        <div>Test Content</div>
      </AuthLayout>
    );

    expect(screen.getByText("Test Content")).toBeInTheDocument();
  });
});
