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

  return (
    <main className="mx-auto max-w-2xl px-8 py-10">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-amber-600 dark:text-amber-400">Historique</p>
          <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-50">Historique</h1>
        </div>
        {(diagnostics.length > 0 || applications.length > 0) && (
          <button
            type="button"
            onClick={() => setIsConfirmOpen(true)}
            className="text-sm font-semibold text-red-600 dark:text-red-400"
          >
            Supprimer tout mon historique
          </button>
        )}
      </div>

      {banner && (
        <div className="mt-4">
          <ErrorBanner content={banner} />
        </div>
      )}

      {applications.length > 0 && (
        <div className="mt-6">
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-50">Candidatures</h2>
          <ul className="mt-3 flex flex-col gap-3">
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
                      <span className="text-sm font-semibold text-slate-900 dark:text-slate-50">
                        {application.job_title} — {application.company_name}
                      </span>
                      <span className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
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

      <div className="mt-8">
        {applications.length > 0 && <h2 className="text-lg font-bold text-slate-900 dark:text-slate-50">Diagnostics</h2>}
        {!isLoading && diagnostics.length === 0 && applications.length === 0 && (
          <div className="mt-6 flex flex-col items-center gap-2 py-10 text-center">
            <Inbox className="h-6 w-6 text-slate-400 dark:text-slate-500" aria-hidden="true" />
            <p className="text-sm text-slate-600 dark:text-slate-400">Aucun diagnostic pour le moment.</p>
          </div>
        )}

        <ul className="mt-3 flex flex-col gap-3">
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
                    <span className="text-sm font-semibold text-slate-900 dark:text-slate-50">
                      {new Date(diagnostic.created_at).toLocaleDateString("fr-FR")}
                    </span>
                    <span className="flex items-center gap-2 text-sm font-bold text-amber-600 dark:text-amber-400">
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
