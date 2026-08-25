"use client";

import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Download, Mail, Sparkles } from "lucide-react";
import { downloadLetter, generateLetter } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Dialog } from "@/components/ui/Dialog";
import { useGenerationJob } from "@/lib/useGenerationJob";
import { AIProgressChecklist } from "@/components/generation/AIProgressChecklist";
import { QualityRatingStars } from "@/components/generation/QualityRatingStars";
import { TonePicker } from "@/components/generation/TonePicker";
import {
  notifyGenerationError,
  notifyGenerationSuccess,
} from "@/components/generation/GenerationFeedbackToast";
import { AiDisclaimerNote } from "@/components/generation/AiDisclaimerNote";
import type { LetterGenerationResult, LetterTone, SavedJobOut } from "@/lib/types";

const LETTER_GENERATION_STEPS = [
  "Analyse de l'offre",
  "Rédaction de la lettre",
  "Mise en page PDF",
];

export function LettreTab({
  savedJob,
  token,
  onGoToCvTab,
}: {
  savedJob: SavedJobOut;
  token: string;
  onGoToCvTab: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [tone, setTone] = useState<LetterTone>("sobre");
  const [rating, setRating] = useState(0);
  const [jobId, setJobId] = useState<string | null>(null);
  const handledJobIdRef = useRef<string | null>(null);

  const { job } = useGenerationJob<LetterGenerationResult>(token, jobId);
  const isGenerating = job?.status === "running" || (!!jobId && !job);

  const existingLetter = savedJob.documents.find((doc) => doc.kind === "lettre");
  const diagnosticId = savedJob.latest_diagnostic?.id;

  useEffect(() => {
    if (!jobId || !job || job.status === "running") return;
    if (handledJobIdRef.current === jobId) return;
    handledJobIdRef.current = jobId;

    if (job.status === "done" && diagnosticId) {
      downloadLetter(token, diagnosticId).then((blob) => {
        setPreviewUrl(URL.createObjectURL(blob));
      });
      notifyGenerationSuccess("Lettre de motivation générée avec succès.");
    } else if (job.status === "error") {
      const message = job.error || "La génération de la lettre a échoué.";
      setError(message);
      notifyGenerationError(message);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job, jobId]);

  if (!diagnosticId) {
    return (
      <Card>
        <CardContent className="p-6">
          <EmptyState
            icon={Mail}
            title="Diagnostic requis"
            description="Lancez d'abord un diagnostic ATS dans l'onglet CV pour pouvoir générer une lettre de motivation sur-mesure."
            action={
              <Button variant="primary" size="sm" onClick={onGoToCvTab}>
                Aller à l'onglet CV
              </Button>
            }
          />
        </CardContent>
      </Card>
    );
  }

  const handleGenerate = async () => {
    setError(null);
    try {
      const started = await generateLetter(token, diagnosticId, tone);
      setJobId(started.job_id);
    } catch (err: any) {
      const message = err?.detail || "La génération de la lettre a échoué.";
      setError(message);
      notifyGenerationError(message);
    }
  };

  const handlePreview = async () => {
    const blob = await downloadLetter(token, diagnosticId);
    setPreviewUrl(URL.createObjectURL(blob));
  };

  const handleDownload = async () => {
    const blob = await downloadLetter(token, diagnosticId);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "lettre_motivation.pdf";
    a.click();
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-xl text-destructive text-xs font-semibold flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      <Card>
        <CardContent className="p-6 space-y-4">
          <p className="text-xs text-muted-foreground">
            Générez une lettre de motivation personnalisée à partir de votre CV et de cette offre.
          </p>

          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            <TonePicker value={tone} onChange={setTone} />
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                isLoading={isGenerating}
                onClick={handleGenerate}
                icon={<Sparkles className="w-4 h-4" />}
              >
                {existingLetter ? "Régénérer la Lettre" : "Rédiger Lettre sur-mesure (IA)"}
              </Button>
              {existingLetter && (
                <>
                  <Button variant="secondary" size="sm" onClick={handlePreview}>
                    Visualiser
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleDownload}
                    icon={<Download className="w-4 h-4" />}
                  />
                </>
              )}
            </div>
          </div>

          {isGenerating && job && (
            <div className="border-t border-border pt-4">
              <AIProgressChecklist
                steps={LETTER_GENERATION_STEPS}
                currentStepIndex={job.step_index}
                status={job.status}
              />
            </div>
          )}

          {job?.status === "done" && (
            <div className="border-t border-border pt-4 space-y-3">
              <AiDisclaimerNote />
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-muted-foreground">Qualité perçue de cette lettre :</p>
                <QualityRatingStars value={rating} onChange={setRating} />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog
        isOpen={!!previewUrl}
        onClose={() => {
          if (previewUrl) URL.revokeObjectURL(previewUrl);
          setPreviewUrl(null);
        }}
        title="Votre Lettre de motivation sur-mesure"
        description="Aperçu direct du document généré par l'IA au format PDF A4 standard."
        className="max-w-4xl w-full"
      >
        <div className="space-y-4 mt-2">
          {previewUrl && (
            <div className="w-full h-[65vh] rounded-xl overflow-hidden border border-border bg-muted/20">
              <iframe src={previewUrl} className="w-full h-full" title="Aperçu Lettre" />
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2 border-t border-border">
            <Button
              variant="primary"
              size="sm"
              icon={<Download className="w-4 h-4" />}
              onClick={handleDownload}
            >
              Télécharger le PDF
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
