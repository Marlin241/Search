"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Download,
  FileCheck2,
  PenLine,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import { createDiagnostic, downloadCv, generateCv, getCandidateProfile } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { Dialog } from "@/components/ui/Dialog";
import { cn, isValidCvFile, MAX_FILE_SIZE } from "@/lib/utils";
import { useGenerationJob } from "@/lib/useGenerationJob";
import { AIProgressChecklist } from "@/components/generation/AIProgressChecklist";
import { HonestyBox } from "@/components/generation/HonestyBox";
import { AtsScoreDelta } from "@/components/generation/AtsScoreDelta";
import { KeywordTransparency } from "@/components/generation/KeywordTransparency";
import { ChangelogList } from "@/components/generation/ChangelogList";
import { TemplatePicker } from "@/components/generation/TemplatePicker";
import { LanguagePicker } from "@/components/generation/LanguagePicker";
import {
  notifyGenerationError,
  notifyGenerationSuccess,
} from "@/components/generation/GenerationFeedbackToast";
import { AiDisclaimerNote } from "@/components/generation/AiDisclaimerNote";
import type { CvTemplate, SavedJobOut } from "@/lib/types";

const CV_GENERATION_STEPS = [
  "Analyse du CV",
  "Génération du contenu",
  "Vérification anti-hallucination",
  "Mise en page PDF",
  "Calcul du score ATS",
];

export function CvTab({
  savedJob,
  token,
  onDiagnosticCreated,
}: {
  savedJob: SavedJobOut;
  token: string;
  onDiagnosticCreated: () => void;
}) {
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isAnalyzingReference, setIsAnalyzingReference] = useState(false);
  const [hasReferenceCv, setHasReferenceCv] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [template, setTemplate] = useState<CvTemplate>("classic");
  const [targetLanguage, setTargetLanguage] = useState("fr");
  const [jobId, setJobId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const { job } = useGenerationJob(token, jobId);
  const isGenerating = job?.status === "running" || (!!jobId && !job);
  const handledJobIdRef = useRef<string | null>(null);

  const existingCv = savedJob.documents.find((doc) => doc.kind === "cv");
  const diagnosticId = savedJob.latest_diagnostic?.id;

  useEffect(() => {
    if (!jobId || !job || job.status === "running") return;
    if (handledJobIdRef.current === jobId) return;
    handledJobIdRef.current = jobId;

    if (job.status === "done" && job.result && diagnosticId) {
      downloadCv(token, diagnosticId).then((blob) => {
        setPreviewUrl(URL.createObjectURL(blob));
      });
      notifyGenerationSuccess("CV optimisé généré avec succès.");
      onDiagnosticCreated();
    } else if (job.status === "error") {
      const message = job.error || "La génération du CV a échoué.";
      setError(message);
      notifyGenerationError(message);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job, jobId]);

  useEffect(() => {
    getCandidateProfile(token)
      .then((profile) => setHasReferenceCv(profile.has_cv))
      .catch(() => setHasReferenceCv(false));
  }, [token]);

  const validateAndSetFile = (file: File) => {
    if (!isValidCvFile(file)) {
      setFileError("Format non supporté. Veuillez choisir un fichier PDF ou DOCX.");
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setFileError("Le fichier est trop volumineux (maximum 5 Mo).");
      return;
    }
    setCvFile(file);
    setFileError(null);
  };

  const handleAnalyze = async () => {
    if (!cvFile) return;
    setIsAnalyzing(true);
    setError(null);
    try {
      await createDiagnostic(token, cvFile, savedJob.snippet, null, savedJob.id);
      onDiagnosticCreated();
    } catch (err: any) {
      setError(err?.detail || "Erreur lors du diagnostic.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleAnalyzeReferenceCv = async () => {
    setIsAnalyzingReference(true);
    setError(null);
    try {
      await createDiagnostic(token, null, savedJob.snippet, null, savedJob.id);
      onDiagnosticCreated();
    } catch (err: any) {
      setError(err?.detail || "Erreur lors du diagnostic.");
    } finally {
      setIsAnalyzingReference(false);
    }
  };

  const handleGenerate = async () => {
    if (!diagnosticId) return;
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
    if (!diagnosticId) return;
    const blob = await downloadCv(token, diagnosticId);
    setPreviewUrl(URL.createObjectURL(blob));
  };

  const handleDownload = async () => {
    if (!diagnosticId) return;
    const blob = await downloadCv(token, diagnosticId);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "cv_optimise.pdf";
    a.click();
  };

  if (!savedJob.latest_diagnostic) {
    return (
      <Card>
        <CardContent className="p-6 space-y-4">
          <p className="text-xs text-muted-foreground">
            Lancez un diagnostic ATS de votre CV pour cette offre afin de débloquer la génération du CV optimisé.
          </p>

          {hasReferenceCv && (
            <Button
              variant="secondary"
              fullWidth
              isLoading={isAnalyzingReference}
              disabled={isAnalyzing}
              icon={<FileCheck2 className="w-4 h-4" />}
              onClick={handleAnalyzeReferenceCv}
            >
              Utiliser mon CV de référence
            </Button>
          )}

          <div
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              "border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-3",
              cvFile ? "border-primary/50 bg-primary/5" : "border-border/80 hover:border-primary/40 hover:bg-muted/30"
            )}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.[0]) validateAndSetFile(e.target.files[0]);
              }}
            />
            <div className="w-10 h-10 rounded-2xl bg-primary/10 text-primary flex items-center justify-center">
              <UploadCloud className="w-5 h-5" />
            </div>
            {cvFile ? (
              <p className="text-sm font-bold text-foreground flex items-center gap-2">
                <FileCheck2 className="w-4 h-4 text-success" />
                {cvFile.name}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Glissez votre CV ici ou <span className="text-primary hover:underline">parcourez vos fichiers</span> (PDF, DOCX, max 5 Mo)
              </p>
            )}
          </div>

          {fileError && <p className="text-xs font-medium text-destructive">{fileError}</p>}
          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-xl text-destructive text-xs font-semibold flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}

          <Button
            variant="primary"
            fullWidth
            disabled={!cvFile || isAnalyzingReference}
            isLoading={isAnalyzing}
            icon={<Sparkles className="w-4 h-4" />}
            onClick={handleAnalyze}
          >
            Lancer le diagnostic ATS
          </Button>
        </CardContent>
      </Card>
    );
  }

  const report = savedJob.latest_diagnostic;

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
            <div className="flex flex-wrap items-center justify-center gap-6">
              <ScoreRing score={report.overall_score} size="lg" label="Score Global" />
              <div className="flex sm:flex-col gap-4">
                <ScoreRing score={report.structural_score} size="sm" label="Structure ATS" />
                <ScoreRing score={report.semantic_score} size="sm" label="Sémantique" />
              </div>
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
                    <Link href={`/offres/${savedJob.id}/cv/editor`}>
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
