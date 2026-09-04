"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Download, FileWarning } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { CvEditorSplitScreen } from "@/components/cv-editor/CvEditorSplitScreen";
import { CvEditorForm } from "@/components/cv-editor/CvEditorForm";
import { StyleControls } from "@/components/cv-editor/StyleControls";
import { CvPreviewFrame } from "@/components/cv-editor/CvPreviewFrame";
import { PageFitWarning } from "@/components/cv-editor/PageFitWarning";
import type { CvStyleOptions, CvTemplate, RewrittenCv } from "@/lib/types";

export function CvEditorShell({
  title,
  backHref,
  backLabel,
  cacheKey,
  loadContent,
  renderPreview,
  emptyStateGoToCvHref,
  notFoundTitle,
  notFoundHref,
  notFoundLabel,
}: {
  title: string;
  backHref: string;
  backLabel: string;
  /** See CvPreviewFrame - identifies the scope so its debounce effect only
   * restarts when the scope itself changes. */
  cacheKey: string;
  loadContent: () => Promise<RewrittenCv | null>;
  renderPreview: (payload: {
    content: RewrittenCv;
    template: CvTemplate;
    style: CvStyleOptions;
  }) => Promise<Blob>;
  emptyStateGoToCvHref: string;
  /** Where to send the user if loadContent itself fails (e.g. the
   * underlying offer/diagnostic no longer exists) - distinct from backHref,
   * which stays valid once content has loaded. */
  notFoundTitle: string;
  notFoundHref: string;
  notFoundLabel: string;
}) {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [content, setContent] = useState<RewrittenCv | null>(null);
  const [template, setTemplate] = useState<CvTemplate>("classic");
  const [style, setStyle] = useState<CvStyleOptions>({
    accent_color: "#2563eb",
    margins: 15,
    spacing: "normal",
  });

  useEffect(() => {
    setIsLoading(true);
    loadContent()
      .then(setContent)
      .catch((err) => setError(err?.detail || "Impossible de charger ce contenu."))
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cacheKey]);

  const handleDownload = async () => {
    if (!content) return;
    const blob = await renderPreview({ content, template, style });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "cv_optimise.pdf";
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-fade-in pb-16 max-w-6xl mx-auto">
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto">
        <EmptyState
          icon={FileWarning}
          title={notFoundTitle}
          description={error}
          action={
            <Link href={notFoundHref}>
              <Button variant="primary" size="sm">
                {notFoundLabel}
              </Button>
            </Link>
          }
        />
      </div>
    );
  }

  if (!content) {
    return (
      <div className="max-w-4xl mx-auto">
        <EmptyState
          icon={FileWarning}
          title="Aucun CV généré"
          description="Générez d'abord un CV optimisé avant de l'éditer."
          action={
            <Link href={emptyStateGoToCvHref}>
              <Button variant="primary" size="sm">
                Aller à l&apos;onglet CV
              </Button>
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in pb-16 max-w-6xl mx-auto">
      <div className="flex items-center justify-between gap-3">
        <Link href={backHref}>
          <Button variant="ghost" size="sm" icon={<ArrowLeft className="w-4 h-4" />}>
            {backLabel}
          </Button>
        </Link>
        <Button
          variant="primary"
          size="sm"
          icon={<Download className="w-4 h-4" />}
          onClick={handleDownload}
        >
          Télécharger
        </Button>
      </div>

      <h1 className="text-xl sm:text-2xl font-display font-bold text-foreground">
        Éditeur de CV — {title}
      </h1>

      <CvEditorSplitScreen
        form={
          <>
            <StyleControls
              template={template}
              onTemplateChange={setTemplate}
              style={style}
              onStyleChange={setStyle}
            />
            <PageFitWarning />
            <CvEditorForm content={content} onChange={setContent} />
          </>
        }
        preview={
          <CvPreviewFrame
            cacheKey={cacheKey}
            renderPreview={renderPreview}
            content={content}
            template={template}
            style={style}
          />
        }
      />
    </div>
  );
}
