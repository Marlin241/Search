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
    <Card className="p-4">
      <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">{title}</p>

      {banner && (
        <div className="mt-2">
          <ErrorBanner content={banner} />
        </div>
      )}

      {!generatedDocument && (
        <Button onClick={handleGenerate} isLoading={isGenerating} size="sm" className="mt-2">
          {isGenerating ? "Génération en cours..." : generatedLabel}
        </Button>
      )}

      {generatedDocument && (
        <div className="mt-2 flex flex-col gap-2">
          <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
            Relisez ce document avant de l&apos;envoyer.
          </p>
          {generatedDocument.needs_review && (
            <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
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
