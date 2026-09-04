"use client";

import { useEffect, useRef, useState } from "react";
import { AlertTriangle, FileCheck2, Sparkles, UploadCloud } from "lucide-react";
import { createDiagnostic, getCandidateProfile } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { cn, isValidCvFile, MAX_FILE_SIZE } from "@/lib/utils";
import { CvGenerationPanel } from "@/components/generation/CvGenerationPanel";
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
  const [isAnalyzingReference, setIsAnalyzingReference] = useState(false);
  const [hasReferenceCv, setHasReferenceCv] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const existingCv = savedJob.documents.find((doc) => doc.kind === "cv");

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
    <CvGenerationPanel
      diagnosticId={report.id as number}
      report={report}
      existingCv={existingCv}
      token={token}
      editorHref={`/offres/${savedJob.id}/cv/editor`}
      onGenerated={onDiagnosticCreated}
    />
  );
}
