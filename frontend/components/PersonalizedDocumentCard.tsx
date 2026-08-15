"use client";

import { useState } from "react";
import { ErrorBanner } from "./ErrorBanner";
import { Card } from "./ui/Card";
import { Button } from "./ui/Button";
import { toBannerContent, type BannerContent } from "@/lib/errors";
import type { PersonalizedDocument } from "@/lib/types";

interface PersonalizedDocumentCardProps {
  title: string;
  generatedLabel: string;
  onGenerate: () => Promise<PersonalizedDocument>;
  onDownload: () => Promise<Blob>;
  downloadFilename: string;
}

export function PersonalizedDocumentCard({
  title,
  generatedLabel,
  onGenerate,
  onDownload,
  downloadFilename,
}: PersonalizedDocumentCardProps) {
  const [generatedDocument, setGeneratedDocument] = useState<PersonalizedDocument | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [banner, setBanner] = useState<BannerContent | null>(null);

  async function handleGenerate() {
    setBanner(null);
    setIsGenerating(true);
    try {
      const result = await onGenerate();
      setGeneratedDocument(result);
    } catch (error) {
      setBanner(toBannerContent(error));
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleDownload() {
    setBanner(null);
    try {
      const blob = await onDownload();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = downloadFilename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setBanner(toBannerContent(error));
    }
  }

  return (
    <Card className="flex flex-col gap-2.5 p-5">
      <p className="text-[14.5px] font-bold text-ink">{title}</p>

      {banner && <ErrorBanner content={banner} />}

      {!generatedDocument && (
        <>
          <p className="text-[13px] text-ink-soft">Une version reformulée par l&apos;IA, prête à relire et ajuster.</p>
          <Button onClick={handleGenerate} isLoading={isGenerating} variant="secondary" size="sm" className="w-fit">
            {isGenerating ? "Génération en cours..." : generatedLabel}
          </Button>
        </>
      )}

      {generatedDocument && (
        <div className="flex flex-col gap-2">
          <p className="rounded-2xl bg-accent-soft px-4 py-2.5 text-sm font-medium text-accent-ink">
            Relisez ce document avant de l&apos;envoyer.
          </p>
          {generatedDocument.needs_review && (
            <p className="rounded-2xl bg-attention-soft px-4 py-2.5 text-sm font-medium text-attention-ink">
              À vérifier : ce document pourrait contenir des éléments absents de votre CV d&apos;origine.
            </p>
          )}
          <div className="flex gap-2">
            <Button onClick={handleDownload} size="sm">
              Télécharger
            </Button>
            <Button onClick={handleGenerate} isLoading={isGenerating} variant="secondary" size="sm">
              {isGenerating ? "Génération en cours..." : "Régénérer"}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
