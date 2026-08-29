"use client";

import { useEffect, useRef, useState } from "react";
import { AlertTriangle, MessagesSquare, RotateCcw } from "lucide-react";
import { getInterviewPrep, startInterviewPrep } from "@/lib/api";
import { ApiError } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useGenerationJob } from "@/lib/useGenerationJob";
import {
  notifyGenerationError,
  notifyGenerationSuccess,
} from "@/components/generation/GenerationFeedbackToast";
import { InterviewPrepLauncher } from "@/components/interview-prep/InterviewPrepLauncher";
import { DossierView, DossierViewProgress } from "@/components/interview-prep/DossierView";
import type { InterviewPrepDossierOut, InterviewPrepRequestIn, SavedJobOut } from "@/lib/types";

export function EntretienTab({
  savedJob,
  token,
  onGoToCvTab,
}: {
  savedJob: SavedJobOut;
  token: string;
  onGoToCvTab: () => void;
}) {
  const [dossier, setDossier] = useState<InterviewPrepDossierOut | null>(null);
  const [isLoadingDossier, setIsLoadingDossier] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [useWebSearch, setUseWebSearch] = useState(false);
  const [showLauncher, setShowLauncher] = useState(false);
  const handledJobIdRef = useRef<string | null>(null);

  const { job } = useGenerationJob<null>(token, jobId);
  const isGenerating = job?.status === "running" || (!!jobId && !job);

  useEffect(() => {
    let cancelled = false;
    setIsLoadingDossier(true);
    getInterviewPrep(token, savedJob.id)
      .then((result) => {
        if (!cancelled) setDossier(result);
      })
      .catch((err) => {
        if (!cancelled && !(err instanceof ApiError && err.status === 404)) {
          setError(err?.detail || "Impossible de charger le dossier de préparation.");
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoadingDossier(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, savedJob.id]);

  useEffect(() => {
    if (!jobId || !job || job.status === "running") return;
    if (handledJobIdRef.current === jobId) return;
    handledJobIdRef.current = jobId;

    if (job.status === "done") {
      getInterviewPrep(token, savedJob.id)
        .then((result) => {
          setDossier(result);
          setShowLauncher(false);
          notifyGenerationSuccess("Dossier de préparation d'entretien généré avec succès.");
        })
        .catch((err) => {
          setError(err?.detail || "Impossible de charger le dossier généré.");
        });
    } else if (job.status === "error") {
      const message = job.error || "La génération du dossier a échoué.";
      setError(message);
      notifyGenerationError(message);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job, jobId]);

  const handleLaunch = async (payload: InterviewPrepRequestIn) => {
    setError(null);
    setUseWebSearch(payload.use_web_search);
    try {
      const started = await startInterviewPrep(token, savedJob.id, payload);
      setJobId(started.job_id);
    } catch (err: any) {
      const message = err?.detail || "La génération du dossier a échoué.";
      setError(message);
      notifyGenerationError(message);
    }
  };

  if (!savedJob.latest_diagnostic) {
    return (
      <Card>
        <CardContent className="p-6">
          <EmptyState
            icon={MessagesSquare}
            title="Diagnostic requis"
            description="Lancez d'abord un diagnostic ATS dans l'onglet CV pour débloquer la préparation d'entretien sur-mesure."
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

  if (isLoadingDossier) {
    return (
      <Card>
        <CardContent className="p-6 space-y-3">
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-xl text-destructive text-xs font-semibold flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {isGenerating && job && (
        <Card>
          <CardContent className="p-6">
            <DossierViewProgress job={job} useWebSearch={useWebSearch} />
          </CardContent>
        </Card>
      )}

      {!isGenerating && dossier && !showLauncher && (
        <>
          <div className="flex justify-end">
            <Button
              variant="secondary"
              size="sm"
              icon={<RotateCcw className="w-4 h-4" />}
              onClick={() => setShowLauncher(true)}
            >
              Régénérer
            </Button>
          </div>
          <Card>
            <CardContent className="p-6">
              <DossierView dossier={dossier} />
            </CardContent>
          </Card>
        </>
      )}

      {!isGenerating && (!dossier || showLauncher) && (
        <Card>
          <CardContent className="p-6 space-y-4">
            <p className="text-xs text-muted-foreground">
              Génère un dossier de préparation sur-mesure : questions probables, exercices
              pratiques et faits sur l&apos;entreprise, ciblés sur ton profil pour cette offre.
            </p>
            <InterviewPrepLauncher isLaunching={isGenerating} onLaunch={handleLaunch} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
