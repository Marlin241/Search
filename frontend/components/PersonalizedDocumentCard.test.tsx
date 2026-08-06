import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { PersonalizedDocumentCard } from "./PersonalizedDocumentCard";
import { ApiError } from "@/lib/api";

const baseProps = {
  title: "CV optimisé",
  generatedLabel: "Générer CV optimisé",
  downloadFilename: "cv_optimise.pdf",
};

describe("PersonalizedDocumentCard", () => {
  it("shows the generate button initially", () => {
    render(<PersonalizedDocumentCard {...baseProps} onGenerate={vi.fn()} onDownload={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Générer CV optimisé" })).toBeInTheDocument();
  });

  it("generates the document and shows the review banner and download button", async () => {
    const onGenerate = vi.fn().mockResolvedValue({
      kind: "cv",
      needs_review: false,
      created_at: "2026-08-06T00:00:00Z",
      updated_at: "2026-08-06T00:00:00Z",
    });
    render(<PersonalizedDocumentCard {...baseProps} onGenerate={onGenerate} onDownload={vi.fn()} />);

    screen.getByRole("button", { name: "Générer CV optimisé" }).click();

    await waitFor(() => expect(onGenerate).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/relisez ce document/i)).toBeInTheDocument();
    expect(screen.queryByText(/à vérifier/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Télécharger" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Régénérer" })).toBeInTheDocument();
  });

  it("shows an additional badge when needs_review is true", async () => {
    const onGenerate = vi.fn().mockResolvedValue({
      kind: "cv",
      needs_review: true,
      created_at: "2026-08-06T00:00:00Z",
      updated_at: "2026-08-06T00:00:00Z",
    });
    render(<PersonalizedDocumentCard {...baseProps} onGenerate={onGenerate} onDownload={vi.fn()} />);

    screen.getByRole("button", { name: "Générer CV optimisé" }).click();

    expect(await screen.findByText(/à vérifier/i)).toBeInTheDocument();
  });

  it("shows an error banner when generation fails", async () => {
    const onGenerate = vi.fn().mockRejectedValue(new ApiError(503, "Le service est indisponible."));
    render(<PersonalizedDocumentCard {...baseProps} onGenerate={onGenerate} onDownload={vi.fn()} />);

    screen.getByRole("button", { name: "Générer CV optimisé" }).click();

    expect(await screen.findByRole("alert")).toHaveTextContent("Le service est indisponible.");
  });

  it("calls onDownload when the download button is clicked", async () => {
    const onGenerate = vi.fn().mockResolvedValue({
      kind: "cv",
      needs_review: false,
      created_at: "2026-08-06T00:00:00Z",
      updated_at: "2026-08-06T00:00:00Z",
    });
    const onDownload = vi.fn().mockResolvedValue(new Blob(["%PDF-1.4"], { type: "application/pdf" }));
    // jsdom doesn't implement createObjectURL/revokeObjectURL — stub them.
    URL.createObjectURL = vi.fn().mockReturnValue("blob:mock-url");
    URL.revokeObjectURL = vi.fn();

    render(<PersonalizedDocumentCard {...baseProps} onGenerate={onGenerate} onDownload={onDownload} />);
    screen.getByRole("button", { name: "Générer CV optimisé" }).click();
    const downloadButton = await screen.findByRole("button", { name: "Télécharger" });

    downloadButton.click();

    await waitFor(() => expect(onDownload).toHaveBeenCalledTimes(1));
  });
});
