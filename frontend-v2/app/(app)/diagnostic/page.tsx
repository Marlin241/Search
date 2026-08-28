"use client";

import { useEffect, useState, useRef } from "react";
import {
  FileText,
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Download,
  FileCheck2,
  Trash2,
  ChevronDown,
  ChevronUp,
  Loader2,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import {
  createDiagnostic,
  listDiagnostics,
  deleteAllDiagnostics,
  generateCv,
  generateLetter,
  downloadCv,
  downloadLetter,
} from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Textarea } from "@/components/ui/Textarea";
import { Input } from "@/components/ui/Input";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { EmptyState } from "@/components/ui/EmptyState";
import { Dialog } from "@/components/ui/Dialog";
import {
  cn,
  formatDate,
  isValidCvFile,
  MAX_FILE_SIZE,
} from "@/lib/utils";
import type { DiagnosticReport } from "@/lib/types";

const LOADING_MESSAGES = [
  "Extraction du texte et détection de la structure...",
  "Analyse sémantique avec l'IA...",
  "Calcul du score ATS et des mots-clés manquants...",
  "Génération des recommandations sur mesure...",
];

export default function DiagnosticPage() {
  const { token } = useAuth();

  // Form states
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [offerMode, setOfferMode] = useState<"text" | "url">("text");
  const [offerText, setOfferText] = useState("");
  const [offerUrl, setOfferUrl] = useState("");
  const [fileError, setFileError] = useState<string | null>(null);

  // Analysis states
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [loadingMsgIdx, setLoadingMsgIdx] = useState(0);
  const [report, setReport] = useState<DiagnosticReport | null>(null);
  const [history, setHistory] = useState<DiagnosticReport[]>([]);

  // Generation states
  const [isGeneratingCv, setIsGeneratingCv] = useState(false);
  const [isGeneratingLetter, setIsGeneratingLetter] = useState(false);
  const [hasCvGenerated, setHasCvGenerated] = useState(false);
  const [hasLetterGenerated, setHasLetterGenerated] = useState(false);

  // Purge modal
  const [isPurgeOpen, setIsPurgeOpen] = useState(false);
  const [isPurging, setIsPurging] = useState(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!token) return;
    listDiagnostics(token)
      .then(setHistory)
      .catch((err) => console.error("Failed to list diagnostics:", err));
  }, [token]);

  // Loading animation text cycling
  useEffect(() => {
    if (!isAnalyzing) return;
    const interval = setInterval(() => {
      setLoadingMsgIdx((prev) => (prev + 1) % LOADING_MESSAGES.length);
    }, 2500);
    return () => clearInterval(interval);
  }, [isAnalyzing]);

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setFileError(null);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

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

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !cvFile) return;

    setIsAnalyzing(true);
    setLoadingMsgIdx(0);
    setReport(null);
    setHasCvGenerated(false);
    setHasLetterGenerated(false);

    try {
      const result = await createDiagnostic(
        token,
        cvFile,
        offerMode === "text" ? offerText : null,
        offerMode === "url" ? offerUrl : null
      );
      setReport(result);
      setHistory((prev) => [result, ...prev]);
    } catch (err: any) {
      console.error("Diagnostic error:", err);
      setFileError(err?.detail || "Erreur lors du diagnostic.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  // PDF Preview State
  const [previewPdfUrl, setPreviewPdfUrl] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState<string>("");
  const [previewKind, setPreviewKind] = useState<"cv" | "lettre">("cv");
  const [generationError, setGenerationError] = useState<string | null>(null);

  const handleGenerateCv = async () => {
    if (!token || !report?.id) return;
    setIsGeneratingCv(true);
    setGenerationError(null);
    try {
      await generateCv(token, report.id);
      setHasCvGenerated(true);
      // Automatically load and open preview
      const blob = await downloadCv(token, report.id);
      const objectUrl = URL.createObjectURL(blob);
      setPreviewPdfUrl(objectUrl);
      setPreviewTitle("Votre CV personnalisé & optimisé ATS");
      setPreviewKind("cv");
    } catch (err: any) {
      console.error("CV generation failed:", err);
      setGenerationError(err?.detail || "La génération du CV a échoué.");
    } finally {
      setIsGeneratingCv(false);
    }
  };

  const handlePreviewCv = async () => {
    if (!token || !report?.id) return;
    try {
      const blob = await downloadCv(token, report.id);
      const objectUrl = URL.createObjectURL(blob);
      setPreviewPdfUrl(objectUrl);
      setPreviewTitle("Votre CV personnalisé & optimisé ATS");
      setPreviewKind("cv");
    } catch (err: any) {
      setGenerationError("Impossible d'afficher l'aperçu du CV.");
    }
  };

  const handleDownloadCv = async () => {
    if (!token || !report?.id) return;
    try {
      const blob = await downloadCv(token, report.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "cv_optimise.pdf";
      a.click();
    } catch (err) {
      console.error("CV download failed:", err);
    }
  };

  const handleGenerateLetter = async () => {
    if (!token || !report?.id) return;
    setIsGeneratingLetter(true);
    setGenerationError(null);
    try {
      await generateLetter(token, report.id);
      setHasLetterGenerated(true);
      // Automatically load and open preview
      const blob = await downloadLetter(token, report.id);
      const objectUrl = URL.createObjectURL(blob);
      setPreviewPdfUrl(objectUrl);
      setPreviewTitle("Votre Lettre de motivation sur-mesure");
      setPreviewKind("lettre");
    } catch (err: any) {
      console.error("Letter generation failed:", err);
      setGenerationError(err?.detail || "La génération de la lettre a échoué.");
    } finally {
      setIsGeneratingLetter(false);
    }
  };

  const handlePreviewLetter = async () => {
    if (!token || !report?.id) return;
    try {
      const blob = await downloadLetter(token, report.id);
      const objectUrl = URL.createObjectURL(blob);
      setPreviewPdfUrl(objectUrl);
      setPreviewTitle("Votre Lettre de motivation sur-mesure");
      setPreviewKind("lettre");
    } catch (err: any) {
      setGenerationError("Impossible d'afficher l'aperçu de la lettre.");
    }
  };

  const handleDownloadLetter = async () => {
    if (!token || !report?.id) return;
    try {
      const blob = await downloadLetter(token, report.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "lettre_motivation.pdf";
      a.click();
    } catch (err) {
      console.error("Letter download failed:", err);
    }
  };

  const handlePurge = async () => {
    if (!token) return;
    setIsPurging(true);
    try {
      await deleteAllDiagnostics(token);
      setHistory([]);
      setReport(null);
      setIsPurgeOpen(false);
    } catch (err) {
      console.error("Purge error:", err);
    } finally {
      setIsPurging(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in pb-16 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-display font-bold text-foreground">
            Diagnostic ATS & Optimisation
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Testez la compatibilité de votre CV et générez vos documents sur-mesure pour chaque offre.
          </p>
        </div>

        {history.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsPurgeOpen(true)}
            icon={<Trash2 className="w-4 h-4 text-destructive" />}
            className="text-xs text-destructive hover:bg-destructive/10"
          >
            Purger l'historique
          </Button>
        )}
      </div>

      {generationError && (
        <div className="p-3.5 bg-destructive/10 border border-destructive/30 rounded-xl text-destructive text-xs font-semibold flex items-center gap-2.5">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{generationError}</span>
        </div>
      )}

      {/* Analysis Form Card */}
      <Card>
        <CardContent className="p-6">
          <form onSubmit={handleAnalyze} className="space-y-6">
            {/* File Dropzone */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Votre CV de référence (PDF ou Word) *
              </label>

              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleFileDrop}
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  "border-2 border-dashed rounded-2xl p-6 sm:p-8 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-3",
                  cvFile
                    ? "border-primary/50 bg-primary/5"
                    : "border-border/80 hover:border-primary/40 hover:bg-muted/30"
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

                <div className="w-12 h-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center">
                  <UploadCloud className="w-6 h-6" />
                </div>

                {cvFile ? (
                  <div className="space-y-1">
                    <p className="text-sm font-bold text-foreground flex items-center justify-center gap-2">
                      <FileCheck2 className="w-4 h-4 text-success" />
                      {cvFile.name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {(cvFile.size / (1024 * 1024)).toFixed(2)} Mo · Cliquez pour changer
                    </p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-foreground">
                      Glissez votre CV ici ou{" "}
                      <span className="text-primary hover:underline">parcourez vos fichiers</span>
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Formats acceptés : PDF, DOCX (Max 5 Mo)
                    </p>
                  </div>
                )}
              </div>

              {fileError && (
                <p className="text-xs font-medium text-destructive">{fileError}</p>
              )}
            </div>

            {/* Offer Target Mode */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Offre ciblée (optionnel)
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setOfferMode("text")}
                    className={cn(
                      "text-xs px-2.5 py-1 rounded-md transition-colors",
                      offerMode === "text"
                        ? "bg-secondary text-foreground font-semibold"
                        : "text-muted-foreground"
                    )}
                  >
                    Texte de l'offre
                  </button>
                  <button
                    type="button"
                    onClick={() => setOfferMode("url")}
                    className={cn(
                      "text-xs px-2.5 py-1 rounded-md transition-colors",
                      offerMode === "url"
                        ? "bg-secondary text-foreground font-semibold"
                        : "text-muted-foreground"
                    )}
                  >
                    URL de l'offre
                  </button>
                </div>
              </div>

              {offerMode === "text" ? (
                <Textarea
                  placeholder="Collez ici la description complète du poste..."
                  value={offerText}
                  onChange={(e) => setOfferText(e.target.value)}
                  className="min-h-[110px]"
                />
              ) : (
                <Input
                  placeholder="https://..."
                  value={offerUrl}
                  onChange={(e) => setOfferUrl(e.target.value)}
                />
              )}
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              fullWidth
              disabled={!cvFile || isAnalyzing}
              isLoading={isAnalyzing}
              icon={<Sparkles className="w-4 h-4" />}
            >
              {isAnalyzing ? "Analyse en cours..." : "Lancer le diagnostic ATS"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Loading state animation */}
      {isAnalyzing && (
        <Card className="p-8 text-center space-y-4 border-primary/30 bg-primary/5 animate-pulse">
          <div className="w-12 h-12 rounded-full bg-primary/10 text-primary mx-auto flex items-center justify-center">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold font-display text-foreground">
              Notre IA analyse votre candidature
            </h3>
            <p className="text-xs text-muted-foreground transition-all">
              {LOADING_MESSAGES[loadingMsgIdx]}
            </p>
          </div>
        </Card>
      )}

      {/* Active Diagnostic Report */}
      {report && (
        <div className="space-y-6 animate-fade-in">
          {/* Score overview & Action buttons */}
          <Card className="p-6 border-primary/20 bg-card shadow-card">
            <div className="flex flex-col lg:flex-row items-center justify-between gap-6">
              {/* Gauges */}
              <div className="flex flex-wrap items-center justify-center gap-6">
                <ScoreRing score={report.overall_score} size="lg" label="Score Global" />
                <div className="flex sm:flex-col gap-4">
                  <ScoreRing score={report.structural_score} size="sm" label="Structure ATS" />
                  <ScoreRing score={report.semantic_score} size="sm" label="Sémantique" />
                </div>
              </div>

              {/* Generation & Preview buttons */}
              <div className="flex flex-col sm:flex-row lg:flex-col gap-3 w-full lg:w-auto">
                <div className="flex items-center gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    className="flex-1"
                    isLoading={isGeneratingCv}
                    onClick={handleGenerateCv}
                    icon={<Sparkles className="w-4 h-4" />}
                  >
                    {hasCvGenerated ? "Régénérer le CV optimisé" : "Générer CV optimisé (IA)"}
                  </Button>
                  {hasCvGenerated && (
                    <>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={handlePreviewCv}
                        title="Aperçu du CV"
                      >
                        Visualiser
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={handleDownloadCv}
                        icon={<Download className="w-4 h-4" />}
                        title="Télécharger le CV PDF"
                      />
                    </>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    className="flex-1"
                    isLoading={isGeneratingLetter}
                    onClick={handleGenerateLetter}
                    icon={<Sparkles className="w-4 h-4 text-primary" />}
                  >
                    {hasLetterGenerated ? "Régénérer la Lettre" : "Rédiger Lettre sur-mesure (IA)"}
                  </Button>
                  {hasLetterGenerated && (
                    <>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={handlePreviewLetter}
                        title="Aperçu de la lettre"
                      >
                        Visualiser
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={handleDownloadLetter}
                        icon={<Download className="w-4 h-4" />}
                        title="Télécharger la Lettre PDF"
                      />
                    </>
                  )}
                </div>
              </div>
            </div>
          </Card>

          {/* Details breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Missing keywords */}
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

            {/* Structural issues */}
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

            {/* Recommendations */}
            <Card className="col-span-full p-5 space-y-3">
              <h3 className="text-sm font-bold font-display text-foreground flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-primary" />
                Conseils personnalisés de notre IA
              </h3>
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
        </div>
      )}

      {/* PDF Document Preview Modal */}
      <Dialog
        isOpen={!!previewPdfUrl}
        onClose={() => {
          if (previewPdfUrl) URL.revokeObjectURL(previewPdfUrl);
          setPreviewPdfUrl(null);
        }}
        title={previewTitle}
        description="Aperçu direct du document généré par l'IA au format PDF A4 standard."
        className="max-w-4xl w-full"
      >
        <div className="space-y-4 mt-2">
          {previewPdfUrl && (
            <div className="w-full h-[65vh] rounded-xl overflow-hidden border border-border bg-muted/20">
              <iframe
                src={previewPdfUrl}
                className="w-full h-full"
                title="Aperçu Document PDF"
              />
            </div>
          )}

          <div className="flex items-center justify-between pt-2 border-t border-border">
            <span className="text-xs text-muted-foreground">
              Document généré prêt à être envoyé aux recruteurs.
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  if (previewPdfUrl) URL.revokeObjectURL(previewPdfUrl);
                  setPreviewPdfUrl(null);
                }}
              >
                Fermer
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={<Download className="w-4 h-4" />}
                onClick={previewKind === "cv" ? handleDownloadCv : handleDownloadLetter}
              >
                Télécharger le PDF
              </Button>
            </div>
          </div>
        </div>
      </Dialog>

      {/* Confirmation Dialog for Purge */}
      <Dialog
        isOpen={isPurgeOpen}
        onClose={() => setIsPurgeOpen(false)}
        title="Purger l'historique des diagnostics"
        description="Cette action est irréversible. Tous vos diagnostics précédents et documents générés associés seront définitivement supprimés (conformité RGPD)."
      >
        <div className="flex justify-end gap-2 pt-4">
          <Button variant="ghost" onClick={() => setIsPurgeOpen(false)}>
            Annuler
          </Button>
          <Button variant="danger" isLoading={isPurging} onClick={handlePurge}>
            Confirmer la purge
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
