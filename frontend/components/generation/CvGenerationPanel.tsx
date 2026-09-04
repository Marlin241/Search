"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Download, PenLine, Sparkles } from "lucide-react";
import { downloadCv, generateCv } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { Dialog } from "@/components/ui/Dialog";
import { useGenerationJob } from "@/lib/useGenerationJob";
import { AIProgressChecklist } from "@/components/generation/AIProgressChecklist";
import { HonestyBox } from "@/components/generation/HonestyBox";
import { AtsScoreDelta } from "@/components/generation/AtsScoreDelta";
import { KeywordTransparency } from "@/components/generation/KeywordTransparency";
import { ChangelogList } from "@/components/generation/ChangelogList";
import { TemplatePicker } from "@/components/generation/TemplatePicker";
import { LanguagePicker } from "@/components/generation/LanguagePicker";
import { ScoreLegend } from "@/components/generation/ScoreLegend";
import {
  notifyGenerationError,
  notifyGenerationSuccess,
} from "@/components/generation/GenerationFeedbackToast";
import { AiDisclaimerNote } from "@/components/generation/AiDisclaimerNote";
import type { CvTemplate, DiagnosticReport, PersonalizedDocumentOut } from "@/lib/types";

const CV_GENERATION_STEPS = [
  "Analyse du CV",
  "Génération du contenu",
  "Vérification anti-hallucination",
  "Mise en page PDF",
  "Calcul du score ATS",
];

export function CvGenerationPanel({
  diagnosticId,
  report,
  existingCv,
  token,
  editorHref,
  onGenerated,
}: {
  diagnosticId: number;
  report: DiagnosticReport;
  existingCv?: PersonalizedDocumentOut;
  token: string;
  editorHref: string;
  onGenerated: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [template, setTemplate] = useState<CvTemplate>("classic");
  const [targetLanguage, setTargetLanguage] = useState("fr");
  const [jobId, setJobId] = useState<string | null>(null);
  const { job } = useGenerationJob(token, jobId);
  const isGenerating = job?.status === "running" || (!!jobId && !job);
  const handledJobIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!jobId || !job || job.status === "running") return;
    if (handledJobIdRef.current === jobId) return;
    handledJobIdRef.current = jobId;

    if (job.status === "done" && job.result) {
      downloadCv(token, diagnosticId).then((blob) => {
        setPreviewUrl(URL.createObjectURL(blob));
      });
      notifyGenerationSuccess("CV optimisé généré avec succès.");
      onGenerated();
    } else if (job.status === "error") {
      const message = job.error || "La génération du CV a échoué.";
      setError(message);
      notifyGenerationError(message);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job, jobId]);

  const handleGenerate = async () => {
    setError(null);
    try {
      const started = await generateCv(token, diagnosticId, template, targetLanguage);
      setJobId(started.job_id);
    } catch (err: any) {
      const message = err?.detail || "La génération du CV a échoué.";
      setError(message);
      notifyGenerationError(message);
    }
  };

  const handlePreview = async () => {
    const blob = await downloadCv(token, diagnosticId);
    setPreviewUrl(URL.createObjectURL(blob));
  };

  const handleDownload = async () => {
    const blob = await downloadCv(token, diagnosticId);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "cv_optimise.pdf";
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

      <Card className="p-6">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
            <div className="flex flex-wrap items-center justify-center gap-2">
              <div className="flex flex-wrap items-center justify-center gap-6">
                <ScoreRing score={report.overall_score} size="lg" label="Score Global" />
                <div className="flex sm:flex-col gap-4">
                  <ScoreRing score={report.structural_score} size="sm" label="Structure ATS" />
                  <ScoreRing score={report.semantic_score} size="sm" label="Sémantique" />
                </div>
              </div>
              <ScoreLegend />
            </div>

            <div className="flex flex-col items-end gap-2">
              <div className="flex items-center gap-2">
                <TemplatePicker value={template} onChange={setTemplate} />
                <LanguagePicker value={targetLanguage} onChange={setTargetLanguage} />
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  isLoading={isGenerating}
                  onClick={handleGenerate}
                  icon={<Sparkles className="w-4 h-4" />}
                >
                  {existingCv ? "Régénérer le CV optimisé" : "Générer CV optimisé (IA)"}
                </Button>
                {existingCv && (
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
                    <Link href={editorHref}>
                      <Button variant="outline" size="sm" icon={<PenLine className="w-4 h-4" />}>
                        Éditer
                      </Button>
                    </Link>
                  </>
                )}
              </div>
            </div>
          </div>

          {isGenerating && job && (
            <div className="border-t border-border pt-4">
              <AIProgressChecklist
                steps={CV_GENERATION_STEPS}
                currentStepIndex={job.step_index}
                status={job.status}
              />
            </div>
          )}
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-5 space-y-3">
          <h3 className="text-sm font-bold font-display text-foreground flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-warning" />
            Mots-clés manquants détectés
          </h3>
          {report.missing_keywords && report.missing_keywords.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {report.missing_keywords.map((kw, i) => (
                <Badge key={i} variant="warning">
                  {kw}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              Aucun mot-clé critique manquant. Votre CV correspond bien au vocabulaire de l'offre.
            </p>
          )}
        </Card>

        <Card className="p-5 space-y-3">
          <h3 className="text-sm font-bold font-display text-foreground flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-warning" />
            Alertes structurelles ATS
          </h3>
          {report.structural_issues && report.structural_issues.length > 0 ? (
            <ul className="space-y-1.5 text-xs text-muted-foreground">
              {report.structural_issues.map((issue, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-warning font-bold">•</span>
                  <span>{issue}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-muted-foreground">
              Formatage idéal pour les robots ATS (pas de tableaux bloquants ni d'images parasites).
            </p>
          )}
        </Card>

        <Card className="md:col-span-2 p-5 space-y-3">
          <h3 className="text-sm font-bold font-display text-foreground flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-primary" />
            Conseils personnalisés de notre IA
          </h3>
          <AiDisclaimerNote />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
            {report.recommendations?.map((rec, i) => (
              <div
                key={i}
                className="p-3.5 rounded-xl bg-muted/40 border border-border/50 text-xs text-foreground/90 space-y-1"
              >
                <span className="font-bold text-primary mr-1.5">0{i + 1}.</span>
                <span>{rec}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {job?.status === "done" && job.result && (
        <div className="space-y-4">
          <Card className="p-6 space-y-4">
            <AiDisclaimerNote />
            <AtsScoreDelta
              before={job.result.ats_score_before}
              after={job.result.ats_score_after}
            />
            <HonestyBox assessment={job.result.content.honesty_assessment} />
            <KeywordTransparency
              added={job.result.content.keywords_added}
              alreadyPresent={job.result.content.keywords_already_present}
              omitted={job.result.content.keywords_deliberately_omitted}
            />
            <ChangelogList entries={job.result.content.changelog} />
          </Card>
        </div>
      )}

      <Dialog
        isOpen={!!previewUrl}
        onClose={() => {
          if (previewUrl) URL.revokeObjectURL(previewUrl);
          setPreviewUrl(null);
        }}
        title="Votre CV personnalisé & optimisé ATS"
        description="Aperçu direct du document généré par l'IA au format PDF A4 standard."
        className="max-w-4xl w-full"
      >
        <div className="space-y-4 mt-2">
          {previewUrl && (
            <div className="w-full h-[65vh] rounded-xl overflow-hidden border border-border bg-muted/20">
              <iframe src={previewUrl} className="w-full h-full" title="Aperçu CV" />
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
