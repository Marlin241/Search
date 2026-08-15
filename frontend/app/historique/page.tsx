"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, Inbox } from "lucide-react";
import { RequireAuth } from "@/components/RequireAuth";
import { DiagnosticReportView } from "@/components/DiagnosticReportView";
import { ApplicationCard } from "@/components/ApplicationCard";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Card } from "@/components/ui/Card";
import { toBannerContent, isSessionExpired, type BannerContent } from "@/lib/errors";
import { listDiagnostics, deleteAllDiagnostics, listApplications } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { Application, DiagnosticReport } from "@/lib/types";

export default function HistoriquePage() {
  return (
    <RequireAuth>
      <HistoriquePageContent />
    </RequireAuth>
  );
}

function HistoriquePageContent() {
  const { token, logout } = useAuth();
  const router = useRouter();
  const [diagnostics, setDiagnostics] = useState<DiagnosticReport[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedApplicationId, setExpandedApplicationId] = useState<number | null>(null);
  const [banner, setBanner] = useState<BannerContent | null>(null);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  function handleAuthError(error: unknown): boolean {
    if (isSessionExpired(error)) {
      logout();
      router.replace("/login");
      return true;
    }
    return false;
  }

  useEffect(() => {
    if (!token) return;
    Promise.all([listDiagnostics(token), listApplications(token)])
      .then(([fetchedDiagnostics, fetchedApplications]) => {
        setDiagnostics(fetchedDiagnostics);
        setApplications(fetchedApplications);
      })
      .catch((error) => {
        if (!handleAuthError(error)) setBanner(toBannerContent(error));
      })
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleDeleteAll() {
    if (!token) return;
    setIsConfirmOpen(false);
    try {
      await deleteAllDiagnostics(token);
      setDiagnostics([]);
      setApplications([]); // RGPD purge cascades to Application rows server-side too
    } catch (error) {
      if (!handleAuthError(error)) setBanner(toBannerContent(error));
    }
  }

  function handleApplicationUpdated(updated: Application) {
    setApplications((prev) => prev.map((application) => (application.id === updated.id ? updated : application)));
  }

  const isEmpty = !isLoading && diagnostics.length === 0 && applications.length === 0;

  return (
    <main className="mx-auto max-w-2xl px-6 py-9 sm:px-8 sm:py-10">
      <div className="relative overflow-hidden rounded-[28px] bg-gradient-to-br from-[oklch(0.75_0.13_85)] to-[oklch(0.68_0.14_70)] px-7 py-7 text-[oklch(0.14_0.02_60)] sm:px-8">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-extrabold uppercase tracking-wide opacity-75">Historique</p>
            <h1 className="mt-1.5 font-display text-3xl font-extrabold tracking-tight">Ton parcours</h1>
          </div>
          {(diagnostics.length > 0 || applications.length > 0) && (
            <button
              type="button"
              onClick={() => setIsConfirmOpen(true)}
              className="pt-1.5 text-[13px] font-bold underline underline-offset-2 opacity-75"
            >
              Supprimer tout mon historique
            </button>
          )}
        </div>
      </div>

      {banner && (
        <div className="mt-4">
          <ErrorBanner content={banner} />
        </div>
      )}

      {isLoading && (
        <div className="mt-6 flex flex-col gap-2.5">
          <div className="skeleton h-[58px] rounded-[18px]" />
          <div className="skeleton h-[58px] rounded-[18px]" />
          <div className="skeleton h-[58px] rounded-[18px]" />
        </div>
      )}

      {isEmpty && (
        <div className="mt-16 flex flex-col items-center gap-3 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-accent-soft">
            <Inbox className="h-6 w-6 text-accent-ink" aria-hidden="true" />
          </div>
          <p className="text-[15px] font-bold text-ink">Aucun diagnostic pour le moment</p>
          <p className="max-w-[280px] text-[13.5px] text-ink-soft">
            Lance ton premier diagnostic pour commencer à suivre tes candidatures ici.
          </p>
        </div>
      )}

      {applications.length > 0 && (
        <div className="mt-6">
          <h2 className="mb-2.5 font-display text-[15px] font-bold text-ink">Candidatures</h2>
          <ul className="flex flex-col gap-3">
            {applications.map((application) => {
              const isExpanded = expandedApplicationId === application.id;
              return (
                <li key={application.id}>
                  <Card className="p-4">
                    <button
                      type="button"
                      onClick={() => setExpandedApplicationId(isExpanded ? null : application.id)}
                      className="flex w-full items-center justify-between text-left"
                    >
                      <span className="text-sm font-bold text-ink">
                        {application.job_title} — {application.company_name}
                      </span>
                      <span className="flex items-center gap-2 text-xs text-ink-faint">
                        {new Date(application.created_at).toLocaleDateString("fr-FR")}
                        <ChevronDown
                          className={`h-4 w-4 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                          aria-hidden="true"
                        />
                      </span>
                    </button>
                    {isExpanded && token && (
                      <div className="mt-4">
                        <ApplicationCard application={application} token={token} onUpdated={handleApplicationUpdated} />
                      </div>
                    )}
                  </Card>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {diagnostics.length > 0 && (
        <div className="mt-7">
          {applications.length > 0 && <h2 className="mb-2.5 font-display text-[15px] font-bold text-ink">Diagnostics</h2>}
          <ul className="flex flex-col gap-2.5">
            {diagnostics.map((diagnostic) => {
              const isExpanded = expandedId === diagnostic.id;
              return (
                <li key={diagnostic.id}>
                  <Card className="p-4">
                    <button
                      type="button"
                      onClick={() => setExpandedId(isExpanded ? null : diagnostic.id)}
                      className="flex w-full items-center justify-between text-left"
                    >
                      <span className="text-sm font-bold text-ink">
                        {new Date(diagnostic.created_at).toLocaleDateString("fr-FR")}
                      </span>
                      <span className="flex items-center gap-2 text-sm font-bold text-accent-strong">
                        {diagnostic.overall_score}/100
                        <ChevronDown
                          className={`h-4 w-4 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                          aria-hidden="true"
                        />
                      </span>
                    </button>
                    {isExpanded && (
                      <div className="mt-4">
                        <DiagnosticReportView report={diagnostic} />
                      </div>
                    )}
                  </Card>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {isConfirmOpen && (
        <ConfirmDialog
          message="Supprimer définitivement tout votre historique de diagnostics et de candidatures ? Cette action est irréversible."
          onConfirm={handleDeleteAll}
          onCancel={() => setIsConfirmOpen(false)}
        />
      )}
    </main>
  );
}
