"use client";

import { useState } from "react";
import { ErrorBanner } from "./ErrorBanner";
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
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <p className="text-sm font-semibold text-slate-900">{title}</p>

      {banner && (
        <div className="mt-2">
          <ErrorBanner content={banner} />
        </div>
      )}

      {!generatedDocument && (
        <button
          type="button"
          onClick={handleGenerate}
          disabled={isGenerating}
          className="mt-2 rounded-md bg-blue-500 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {isGenerating ? "Génération en cours..." : generatedLabel}
        </button>
      )}

      {generatedDocument && (
        <div className="mt-2 flex flex-col gap-2">
          <p className="rounded-md border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-800">
            Relisez ce document avant de l&apos;envoyer.
          </p>
          {generatedDocument.needs_review && (
            <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              À vérifier : ce document pourrait contenir des éléments absents de votre CV d&apos;origine.
            </p>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleDownload}
              className="rounded-md bg-blue-500 px-3 py-2 text-sm font-semibold text-white"
            >
              Télécharger
            </button>
            <button
              type="button"
              onClick={handleGenerate}
              disabled={isGenerating}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50"
            >
              {isGenerating ? "Génération en cours..." : "Régénérer"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
