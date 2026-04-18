import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TriageBadge } from "../components/TriageBadge";

describe("TriageBadge", () => {
  it("renders Critical label for critical severity", () => {
    render(<TriageBadge severity="critical" />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it("renders Warning label for warning severity", () => {
    render(<TriageBadge severity="warning" />);
    expect(screen.getByText("Warning")).toBeInTheDocument();
  });

  it("renders Info label for info severity", () => {
    render(<TriageBadge severity="info" />);
    expect(screen.getByText("Info")).toBeInTheDocument();
  });

  it("has aria-label Severity: Critical for critical severity", () => {
    render(<TriageBadge severity="critical" />);
    expect(screen.getByLabelText("Severity: Critical")).toBeInTheDocument();
  });

  it("has aria-label Severity: Warning for warning severity", () => {
    render(<TriageBadge severity="warning" />);
    expect(screen.getByLabelText("Severity: Warning")).toBeInTheDocument();
  });

  it("has aria-label Severity: Informational for info severity", () => {
    render(<TriageBadge severity="info" />);
    expect(screen.getByLabelText("Severity: Informational")).toBeInTheDocument();
  });

  it("backward compat: high renders same as critical", () => {
    render(<TriageBadge severity="high" />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByLabelText("Severity: Critical")).toBeInTheDocument();
  });

  it("backward compat: medium renders same as warning", () => {
    render(<TriageBadge severity="medium" />);
    expect(screen.getByText("Warning")).toBeInTheDocument();
    expect(screen.getByLabelText("Severity: Warning")).toBeInTheDocument();
  });

  it("backward compat: low renders same as info", () => {
    render(<TriageBadge severity="low" />);
    expect(screen.getByText("Info")).toBeInTheDocument();
    expect(screen.getByLabelText("Severity: Informational")).toBeInTheDocument();
  });
});
