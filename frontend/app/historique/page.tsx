"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import { DiagnosticReportView } from "@/components/DiagnosticReportView";
import { ApplicationCard } from "@/components/ApplicationCard";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ConfirmDialog } from "@/components/ConfirmDialog";
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
    <main className="mx-auto max-w-2xl px-6 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900">Historique</h1>
        {(diagnostics.length > 0 || applications.length > 0) && (
          <button type="button" onClick={() => setIsConfirmOpen(true)} className="text-sm font-semibold text-red-600">
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
          <h2 className="text-lg font-bold text-slate-900">Candidatures</h2>
          <ul className="mt-3 flex flex-col gap-3">
            {applications.map((application) => (
              <li key={application.id} className="rounded-xl bg-white p-4 shadow-sm">
                <button
                  type="button"
                  onClick={() => setExpandedApplicationId(expandedApplicationId === application.id ? null : application.id)}
                  className="flex w-full items-center justify-between text-left"
                >
                  <span className="text-sm font-semibold text-slate-900">
                    {application.job_title} — {application.company_name}
                  </span>
                  <span className="text-xs text-slate-500">
                    {new Date(application.created_at).toLocaleDateString("fr-FR")}
                  </span>
                </button>
                {expandedApplicationId === application.id && token && (
                  <div className="mt-4">
                    <ApplicationCard application={application} token={token} onUpdated={handleApplicationUpdated} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-8">
        {applications.length > 0 && <h2 className="text-lg font-bold text-slate-900">Diagnostics</h2>}
        {!isLoading && diagnostics.length === 0 && applications.length === 0 && (
          <p className="mt-6 text-sm text-slate-600">Aucun diagnostic pour le moment.</p>
        )}

        <ul className="mt-3 flex flex-col gap-3">
          {diagnostics.map((diagnostic) => (
            <li key={diagnostic.id} className="rounded-xl bg-white p-4 shadow-sm">
              <button
                type="button"
                onClick={() => setExpandedId(expandedId === diagnostic.id ? null : diagnostic.id)}
                className="flex w-full items-center justify-between text-left"
              >
                <span className="text-sm font-semibold text-slate-900">
                  {new Date(diagnostic.created_at).toLocaleDateString("fr-FR")}
                </span>
                <span className="text-sm font-bold text-blue-600">{diagnostic.overall_score}/100</span>
              </button>
              {expandedId === diagnostic.id && (
                <div className="mt-4">
                  <DiagnosticReportView report={diagnostic} />
                </div>
              )}
            </li>
          ))}
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
