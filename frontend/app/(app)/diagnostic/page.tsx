"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  UploadCloud,
  AlertTriangle,
  Sparkles,
  FileCheck2,
  Trash2,
  ChevronDown,
  ChevronUp,
  Loader2,
  History,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { createDiagnostic, getDiagnostic, listDiagnostics, deleteAllDiagnostics } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Textarea } from "@/components/ui/Textarea";
import { Input } from "@/components/ui/Input";
import { EmptyState } from "@/components/ui/EmptyState";
import { Dialog } from "@/components/ui/Dialog";
import { CvGenerationPanel } from "@/components/generation/CvGenerationPanel";
import { LetterGenerationPanel } from "@/components/generation/LetterGenerationPanel";
import {
  cn,
  formatDate,
  isValidCvFile,
  scoreColor,
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

  // Purge modal
  const [isPurgeOpen, setIsPurgeOpen] = useState(false);
  const [isPurging, setIsPurging] = useState(false);

  // History panel
  const [isHistoryOpen, setIsHistoryOpen] = useState(true);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const reportSectionRef = useRef<HTMLDivElement | null>(null);

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

    try {
      const result = await createDiagnostic(
        token,
        cvFile,
        offerMode === "text" ? offerText : null,
        offerMode === "url" ? offerUrl : null
      );
      setReport(result);
      setHistory((prev) => [result, ...prev]);
      requestAnimationFrame(() => {
        reportSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    } catch (err: any) {
      console.error("Diagnostic error:", err);
      setFileError(err?.detail || "Erreur lors du diagnostic.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleSelectHistoryItem = (item: DiagnosticReport) => {
    setReport(item);
    requestAnimationFrame(() => {
      reportSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  // Reloads the active report's documents (called after a CV/lettre
  // generation) so the "Régénérer/Visualiser/Éditer" state reflects what
  // was just generated, both for the displayed report and its history row -
  // same pattern as the workspace's CvTab/LettreTab `refresh()`.
  const refreshReport = useCallback(async () => {
    if (!token || !report?.id) return;
    const updated = await getDiagnostic(token, report.id);
    setReport(updated);
    setHistory((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
  }, [token, report?.id]);

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

  const existingCv = report?.documents.find((doc) => doc.kind === "cv");
  const existingLetter = report?.documents.find((doc) => doc.kind === "lettre");

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

      {/* History Panel */}
      {history.length > 0 && (
        <Card>
          <CardContent className="p-0">
            <button
              type="button"
              onClick={() => setIsHistoryOpen((v) => !v)}
              className="w-full flex items-center justify-between px-5 py-4 text-left"
            >
              <div className="flex items-center gap-2.5">
                <History className="w-4 h-4 text-primary" />
                <span className="text-sm font-bold font-display text-foreground">
                  Historique des diagnostics
                </span>
                <Badge variant="default">{history.length}</Badge>
              </div>
              {isHistoryOpen ? (
                <ChevronUp className="w-4 h-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="w-4 h-4 text-muted-foreground" />
              )}
            </button>

            {isHistoryOpen && (
              <div className="border-t border-border/60 divide-y divide-border/60 max-h-72 overflow-y-auto">
                {history.map((item) => {
                  const isActive = report?.id === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => handleSelectHistoryItem(item)}
                      className={cn(
                        "w-full flex items-center justify-between gap-4 px-5 py-3 text-left transition-colors",
                        isActive ? "bg-primary/5" : "hover:bg-muted/40"
                      )}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <span
                          className={cn(
                            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted/60 text-xs font-bold font-display",
                            scoreColor(item.overall_score)
                          )}
                        >
                          {item.overall_score}
                        </span>
                        <div className="min-w-0">
                          <p className="text-xs font-semibold text-foreground truncate">
                            Diagnostic du {formatDate(item.created_at)}
                          </p>
                          <p className="text-[11px] text-muted-foreground">
                            {item.missing_keywords?.length ?? 0} mot(s)-clé(s) manquant(s)
                          </p>
                        </div>
                      </div>
                      {isActive && (
                        <Badge variant="accent" className="shrink-0">
                          Affiché
                        </Badge>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
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
      {report && token && (
        <div ref={reportSectionRef} className="space-y-6 animate-fade-in scroll-mt-6">
          <CvGenerationPanel
            diagnosticId={report.id as number}
            report={report}
            existingCv={existingCv}
            token={token}
            editorHref={`/diagnostic/${report.id}/cv/editor`}
            onGenerated={refreshReport}
          />
          <LetterGenerationPanel
            diagnosticId={report.id as number}
            existingLetter={existingLetter}
            token={token}
          />
        </div>
      )}

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
