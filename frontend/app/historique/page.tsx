"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import { DiagnosticReportView } from "@/components/DiagnosticReportView";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { toBannerContent, isSessionExpired, type BannerContent } from "@/lib/errors";
import { listDiagnostics, deleteAllDiagnostics } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { DiagnosticReport } from "@/lib/types";

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
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [banner, setBanner] = useState<BannerContent | null>(null);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    listDiagnostics(token)
      .then(setDiagnostics)
      .catch((error) => {
        if (isSessionExpired(error)) {
          logout();
          router.replace("/login");
          return;
        }
        setBanner(toBannerContent(error));
      })
      .finally(() => setIsLoading(false));
  }, [token, logout, router]);

  async function handleDeleteAll() {
    if (!token) return;
    setIsConfirmOpen(false);
    try {
      await deleteAllDiagnostics(token);
      setDiagnostics([]);
    } catch (error) {
      if (isSessionExpired(error)) {
        logout();
        router.replace("/login");
        return;
      }
      setBanner(toBannerContent(error));
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900">Historique</h1>
        {diagnostics.length > 0 && (
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

      {!isLoading && diagnostics.length === 0 && (
        <p className="mt-6 text-sm text-slate-600">Aucun diagnostic pour le moment.</p>
      )}

      <ul className="mt-6 flex flex-col gap-3">
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

      {isConfirmOpen && (
        <ConfirmDialog
          message="Supprimer définitivement tout votre historique de diagnostics ? Cette action est irréversible."
          onConfirm={handleDeleteAll}
          onCancel={() => setIsConfirmOpen(false)}
        />
      )}
    </main>
  );
}
