"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Download, FileWarning } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { getSavedJob, renderCvPreview } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { CvEditorSplitScreen } from "@/components/cv-editor/CvEditorSplitScreen";
import { CvEditorForm } from "@/components/cv-editor/CvEditorForm";
import { StyleControls } from "@/components/cv-editor/StyleControls";
import { CvPreviewFrame } from "@/components/cv-editor/CvPreviewFrame";
import { PageFitWarning } from "@/components/cv-editor/PageFitWarning";
import type { CvStyleOptions, CvTemplate, RewrittenCv, SavedJobOut } from "@/lib/types";

export default function CvEditorPage() {
  const { token } = useAuth();
  const router = useRouter();
  const params = useParams<{ savedJobId: string }>();
  const savedJobId = Number(params.savedJobId);

  const [savedJob, setSavedJob] = useState<SavedJobOut | null>(null);
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
    if (!token || Number.isNaN(savedJobId)) return;
    setIsLoading(true);
    getSavedJob(token, savedJobId)
      .then((job) => {
        setSavedJob(job);
        const cvDocument = job.documents.find((doc) => doc.kind === "cv");
        if (cvDocument?.content_json) {
          setContent(cvDocument.content_json);
        }
      })
      .catch((err) => setError(err?.detail || "Impossible de charger cette offre."))
      .finally(() => setIsLoading(false));
  }, [token, savedJobId]);

  const handleDownload = async () => {
    if (!token || !content) return;
    const blob = await renderCvPreview(token, savedJobId, { content, template, style });
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

  if (error || !savedJob) {
    return (
      <div className="max-w-4xl mx-auto">
        <EmptyState
          icon={FileWarning}
          title="Offre introuvable"
          description={error || "Cette offre sauvegardée n'existe pas ou plus."}
          action={
            <Button variant="primary" size="sm" onClick={() => router.push("/offres")}>
              Retour aux offres
            </Button>
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
          title="Aucun CV généré pour cette offre"
          description="Générez d'abord un CV optimisé depuis l'onglet CV avant de l'éditer."
          action={
            <Button
              variant="primary"
              size="sm"
              onClick={() => router.push(`/offres/${savedJobId}?tab=cv`)}
            >
              Aller à l&apos;onglet CV
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in pb-16 max-w-6xl mx-auto">
      <div className="flex items-center justify-between gap-3">
        <Button
          variant="ghost"
          size="sm"
          icon={<ArrowLeft className="w-4 h-4" />}
          onClick={() => router.push(`/offres/${savedJobId}?tab=cv`)}
        >
          Retour à l&apos;offre
        </Button>
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
        Éditeur de CV — {savedJob.title}
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
          token && (
            <CvPreviewFrame
              token={token}
              savedJobId={savedJobId}
              content={content}
              template={template}
              style={style}
            />
          )
        }
      />
    </div>
  );
}
