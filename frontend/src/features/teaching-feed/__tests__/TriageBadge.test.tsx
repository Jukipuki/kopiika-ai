import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TriageBadge } from "../components/TriageBadge";

describe("TriageBadge", () => {
  it("renders High Priority label and icon for high severity", () => {
    render(<TriageBadge severity="high" />);
    expect(screen.getByText("High Priority")).toBeInTheDocument();
    expect(screen.getByText("🔴")).toBeInTheDocument();
  });

  it("renders Medium label and icon for medium severity", () => {
    render(<TriageBadge severity="medium" />);
    expect(screen.getByText("Medium")).toBeInTheDocument();
    expect(screen.getByText("🟡")).toBeInTheDocument();
  });

  it("renders Low label and icon for low severity", () => {
    render(<TriageBadge severity="low" />);
    expect(screen.getByText("Low")).toBeInTheDocument();
    expect(screen.getByText("🟢")).toBeInTheDocument();
  });

  it("has aria-label on the badge for high severity", () => {
    render(<TriageBadge severity="high" />);
    expect(screen.getByLabelText("High priority insight")).toBeInTheDocument();
  });

  it("has aria-label on the badge for medium severity", () => {
    render(<TriageBadge severity="medium" />);
    expect(screen.getByLabelText("Medium priority insight")).toBeInTheDocument();
  });

  it("has aria-label on the badge for low severity", () => {
    render(<TriageBadge severity="low" />);
    expect(screen.getByLabelText("Low priority insight")).toBeInTheDocument();
  });
});
