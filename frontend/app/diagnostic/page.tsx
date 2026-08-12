"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import { CVDropzone } from "@/components/CVDropzone";
import { OfferInput, EMPTY_OFFER_VALUE, type OfferInputValue } from "@/components/OfferInput";
import { DiagnosticReportView } from "@/components/DiagnosticReportView";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PersonalizedDocumentCard } from "@/components/PersonalizedDocumentCard";
import { Button } from "@/components/ui/Button";
import { toBannerContent, isSessionExpired, type BannerContent } from "@/lib/errors";
import { createDiagnostic, downloadCv, downloadLetter, generateCv, generateLetter } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { DiagnosticReport } from "@/lib/types";

export default function DiagnosticPage() {
  return (
    <RequireAuth>
      <DiagnosticPageContent />
    </RequireAuth>
  );
}

function DiagnosticPageContent() {
  const { token, logout } = useAuth();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [offer, setOffer] = useState<OfferInputValue>(EMPTY_OFFER_VALUE);
  const [report, setReport] = useState<DiagnosticReport | null>(null);
  const [banner, setBanner] = useState<BannerContent | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canSubmit =
    Boolean(file) && (offer.mode === "text" ? offer.text.trim().length > 0 : offer.url.trim().length > 0);

  async function handleSubmit() {
    if (!token || !file) return;
    setBanner(null);
    setIsSubmitting(true);
    try {
      const result = await createDiagnostic(token, file, {
        text: offer.mode === "text" ? offer.text.trim() || undefined : undefined,
        url: offer.mode === "url" ? offer.url.trim() || undefined : undefined,
      });
      setReport(result);
    } catch (error) {
      if (isSessionExpired(error)) {
        logout();
        router.replace("/login");
        return;
      }
      setBanner(toBannerContent(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-8 py-10">
      <p className="text-xs font-bold uppercase tracking-wide text-amber-600 dark:text-amber-400">Diagnostic</p>
      <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-50">Analyser un CV</h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
        Uploadez votre CV et l&apos;offre visée pour comprendre ce qui bloque côté ATS.
      </p>

      <div className="mt-6 flex flex-col gap-4">
        <CVDropzone file={file} onFileSelected={setFile} />
        <OfferInput value={offer} onChange={setOffer} />
        {banner && <ErrorBanner content={banner} />}
        <Button onClick={handleSubmit} disabled={!canSubmit} isLoading={isSubmitting} className="w-fit">
          {isSubmitting ? "Analyse en cours, ça prend quelques secondes..." : "Analyser mon CV"}
        </Button>
      </div>

      {report && (
        <div className="mt-10 flex flex-col gap-6">
          <DiagnosticReportView report={report} />
          {token && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <PersonalizedDocumentCard
                title="CV optimisé"
                generatedLabel="Générer CV optimisé"
                onGenerate={() => generateCv(token, report.id)}
                onDownload={() => downloadCv(token, report.id)}
                downloadFilename="cv_optimise.pdf"
              />
              <PersonalizedDocumentCard
                title="Lettre de motivation"
                generatedLabel="Générer lettre de motivation"
                onGenerate={() => generateLetter(token, report.id)}
                onDownload={() => downloadLetter(token, report.id)}
                downloadFilename="lettre_motivation.pdf"
              />
            </div>
          )}
        </div>
      )}
    </main>
  );
}
