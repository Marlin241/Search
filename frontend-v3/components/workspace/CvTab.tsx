"use client";

import { useRef, useState } from "react";
import { AlertTriangle, Download, FileCheck2, Sparkles, UploadCloud } from "lucide-react";
import { createDiagnostic, downloadCv, generateCv } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { Dialog } from "@/components/ui/Dialog";
import { cn, isValidCvFile, MAX_FILE_SIZE } from "@/lib/utils";
import type { SavedJobOut } from "@/lib/types";

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
  const [isGenerating, setIsGenerating] = useState(false);
  const [hasCvGenerated, setHasCvGenerated] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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
      await createDiagnostic(
        token,
        cvFile,
        savedJob.snippet,
        null,
        savedJob.id
      );
      onDiagnosticCreated();
    } catch (err: any) {
      setError(err?.detail || "Erreur lors du diagnostic.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const diagnosticId = savedJob.latest_diagnostic?.id;

  const handleGenerate = async () => {
    if (!diagnosticId) return;
    setIsGenerating(true);
    setError(null);
    try {
      await generateCv(token, diagnosticId);
      setHasCvGenerated(true);
      const blob = await downloadCv(token, diagnosticId);
      setPreviewUrl(URL.createObjectURL(blob));
    } catch (err: any) {
      setError(err?.detail || "La génération du CV a échoué.");
    } finally {
      setIsGenerating(false);
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
            disabled={!cvFile}
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
        <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex flex-wrap items-center justify-center gap-6">
            <ScoreRing score={report.overall_score} size="lg" label="Score Global" />
            <div className="flex sm:flex-col gap-4">
              <ScoreRing score={report.structural_score} size="sm" label="Structure ATS" />
              <ScoreRing score={report.semantic_score} size="sm" label="Sémantique" />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="primary"
              size="sm"
              isLoading={isGenerating}
              onClick={handleGenerate}
              icon={<Sparkles className="w-4 h-4" />}
            >
              {hasCvGenerated ? "Régénérer le CV optimisé" : "Générer CV optimisé (IA)"}
            </Button>
            {hasCvGenerated && (
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
      </Card>

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
