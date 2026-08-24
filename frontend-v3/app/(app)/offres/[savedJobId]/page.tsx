"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Building } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { getSavedJob } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { getInitials, sourceLabel } from "@/lib/utils";
import { JobWorkspaceTabs, type WorkspaceTab } from "@/components/workspace/JobWorkspaceTabs";
import { OffreTab } from "@/components/workspace/OffreTab";
import { CvTab } from "@/components/workspace/CvTab";
import { LettreTab } from "@/components/workspace/LettreTab";
import { EntretienTab } from "@/components/workspace/EntretienTab";
import type { SavedJobOut } from "@/lib/types";

const VALID_TABS: WorkspaceTab[] = ["offre", "cv", "lettre", "entretien"];

export default function JobWorkspacePage() {
  const { token } = useAuth();
  const router = useRouter();
  const params = useParams<{ savedJobId: string }>();
  const searchParams = useSearchParams();
  const savedJobId = Number(params.savedJobId);

  const tabParam = searchParams.get("tab");
  const activeTab: WorkspaceTab = VALID_TABS.includes(tabParam as WorkspaceTab)
    ? (tabParam as WorkspaceTab)
    : "offre";

  const [savedJob, setSavedJob] = useState<SavedJobOut | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    if (!token || Number.isNaN(savedJobId)) return;
    return getSavedJob(token, savedJobId)
      .then(setSavedJob)
      .catch((err) => setError(err?.detail || "Impossible de charger cette offre."));
  }, [token, savedJobId]);

  useEffect(() => {
    if (!token || Number.isNaN(savedJobId)) return;
    setIsLoading(true);
    getSavedJob(token, savedJobId)
      .then(setSavedJob)
      .catch((err) => setError(err?.detail || "Impossible de charger cette offre."))
      .finally(() => setIsLoading(false));
  }, [token, savedJobId]);

  const setTab = (tab: WorkspaceTab) => {
    router.replace(`/offres/${savedJobId}?tab=${tab}`);
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-fade-in pb-16 max-w-4xl mx-auto">
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (error || !savedJob) {
    return (
      <div className="max-w-4xl mx-auto">
        <EmptyState
          icon={Building}
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

  return (
    <div className="space-y-6 animate-fade-in pb-16 max-w-4xl mx-auto">
      <Button
        variant="ghost"
        size="sm"
        icon={<ArrowLeft className="w-4 h-4" />}
        onClick={() => router.push("/offres")}
      >
        Retour aux offres
      </Button>

      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-primary/10 text-primary font-bold text-sm flex items-center justify-center shrink-0">
          {getInitials(savedJob.company)}
        </div>
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-display font-bold text-foreground truncate">
            {savedJob.title}
          </h1>
          <p className="text-sm text-muted-foreground truncate">
            {savedJob.company} · {sourceLabel(savedJob.source)}
          </p>
        </div>
      </div>

      <JobWorkspaceTabs active={activeTab} onChange={setTab} />

      {activeTab === "offre" && <OffreTab savedJob={savedJob} />}
      {activeTab === "cv" && token && (
        <CvTab savedJob={savedJob} token={token} onDiagnosticCreated={refresh} />
      )}
      {activeTab === "lettre" && token && (
        <LettreTab savedJob={savedJob} token={token} onGoToCvTab={() => setTab("cv")} />
      )}
      {activeTab === "entretien" && <EntretienTab />}
    </div>
  );
}
