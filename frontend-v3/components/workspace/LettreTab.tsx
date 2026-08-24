"use client";

import { useState } from "react";
import { AlertTriangle, Download, Sparkles } from "lucide-react";
import { downloadLetter, generateLetter } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Dialog } from "@/components/ui/Dialog";
import { Mail } from "lucide-react";
import type { SavedJobOut } from "@/lib/types";

export function LettreTab({
  savedJob,
  token,
  onGoToCvTab,
}: {
  savedJob: SavedJobOut;
  token: string;
  onGoToCvTab: () => void;
}) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [hasLetterGenerated, setHasLetterGenerated] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const diagnosticId = savedJob.latest_diagnostic?.id;

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
    setIsGenerating(true);
    setError(null);
    try {
      await generateLetter(token, diagnosticId);
      setHasLetterGenerated(true);
      const blob = await downloadLetter(token, diagnosticId);
      setPreviewUrl(URL.createObjectURL(blob));
    } catch (err: any) {
      setError(err?.detail || "La génération de la lettre a échoué.");
    } finally {
      setIsGenerating(false);
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
          <div className="flex items-center gap-2">
            <Button
              variant="primary"
              size="sm"
              isLoading={isGenerating}
              onClick={handleGenerate}
              icon={<Sparkles className="w-4 h-4" />}
            >
              {hasLetterGenerated ? "Régénérer la Lettre" : "Rédiger Lettre sur-mesure (IA)"}
            </Button>
            {hasLetterGenerated && (
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
