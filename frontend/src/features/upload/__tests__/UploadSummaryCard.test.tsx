import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";
import UploadSummaryCard from "../components/UploadSummaryCard";

vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

describe("UploadSummaryCard", () => {
  const baseProps = {
    bankName: "Monobank",
    transactionCount: 245,
    dateRange: { start: "2026-02-01", end: "2026-02-28" },
    totalInsights: 12,
    duplicatesSkipped: 3,
    newTransactions: 245,
    fallbackBankLabel: "Bank statement detected",
    onUploadAnother: () => {},
  };

  it("renders title and bank-detected line using bankName", () => {
    render(<UploadSummaryCard {...baseProps} />);

    expect(screen.getByText("Your statement is ready")).toBeInTheDocument();
    expect(screen.getByText("Monobank statement detected")).toBeInTheDocument();
  });

  it("renders View Insights link pointing to /feed", () => {
    render(<UploadSummaryCard {...baseProps} />);

    const link = screen.getByRole("link", { name: /View Insights/i });
    expect(link).toHaveAttribute("href", "/feed");
  });

  it("renders transaction count, insight count, and date range", () => {
    render(<UploadSummaryCard {...baseProps} />);

    // Transaction count rendered with the count substituted (i18n mock replaces {count...})
    expect(screen.getAllByText(/245/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/12/).length).toBeGreaterThan(0);
    // Date range line should be present (formatted for en-US locale)
    expect(screen.getByText(/–/)).toBeInTheDocument();
  });

  it("hides date-range line when dateRange is null", () => {
    render(<UploadSummaryCard {...baseProps} dateRange={null} />);

    expect(screen.queryByText(/–/)).not.toBeInTheDocument();
  });

  it("falls back to fallbackBankLabel when bankName is missing", () => {
    render(
      <UploadSummaryCard
        {...baseProps}
        bankName={null}
        fallbackBankLabel="Bank statement detected"
      />,
    );

    expect(screen.getByText("Bank statement detected")).toBeInTheDocument();
    expect(screen.queryByText(/Monobank statement detected/)).not.toBeInTheDocument();
  });

  it("calls onUploadAnother when the secondary button is clicked", async () => {
    const onUploadAnother = vi.fn();
    render(<UploadSummaryCard {...baseProps} onUploadAnother={onUploadAnother} />);

    await userEvent.click(screen.getByRole("button", { name: /Upload another/i }));
    expect(onUploadAnother).toHaveBeenCalledOnce();
  });

  it("renders View upload history link", () => {
    render(<UploadSummaryCard {...baseProps} />);

    const link = screen.getByRole("link", { name: /View upload history/i });
    expect(link).toHaveAttribute("href", "/history");
  });
});
