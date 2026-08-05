import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { DiagnosticReportView } from "./DiagnosticReportView";
import type { DiagnosticReport } from "@/lib/types";

const baseReport: DiagnosticReport = {
  id: 1,
  created_at: "2026-08-05T10:00:00Z",
  overall_score: 62,
  structural_score: 80,
  structural_issues: ["Mise en page 2 colonnes détectée."],
  semantic_score: 44,
  missing_keywords: ["Docker", "Kubernetes"],
  recommendations: ["Ajoutez une section Compétences plus détaillée."],
};

describe("DiagnosticReportView", () => {
  it("renders the three scores", () => {
    render(<DiagnosticReportView report={baseReport} />);
    expect(screen.getByText("62")).toBeInTheDocument();
    expect(screen.getByText("80")).toBeInTheDocument();
    expect(screen.getByText("44")).toBeInTheDocument();
  });

  it("renders structural issues", () => {
    render(<DiagnosticReportView report={baseReport} />);
    expect(screen.getByText("Mise en page 2 colonnes détectée.")).toBeInTheDocument();
  });

  it("renders missing keywords", () => {
    render(<DiagnosticReportView report={baseReport} />);
    expect(screen.getByText("Docker")).toBeInTheDocument();
    expect(screen.getByText("Kubernetes")).toBeInTheDocument();
  });

  it("renders recommendations", () => {
    render(<DiagnosticReportView report={baseReport} />);
    expect(screen.getByText("Ajoutez une section Compétences plus détaillée.")).toBeInTheDocument();
  });

  it("shows an empty-state message when there are no structural issues", () => {
    render(<DiagnosticReportView report={{ ...baseReport, structural_issues: [] }} />);
    expect(screen.getByText("Aucun problème structurel détecté.")).toBeInTheDocument();
  });

  it("shows an empty-state message when there are no missing keywords", () => {
    render(<DiagnosticReportView report={{ ...baseReport, missing_keywords: [] }} />);
    expect(screen.getByText("Aucun mot-clé manquant détecté.")).toBeInTheDocument();
  });
});
