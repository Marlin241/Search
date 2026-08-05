"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import { CVDropzone } from "@/components/CVDropzone";
import { OfferInput, EMPTY_OFFER_VALUE, type OfferInputValue } from "@/components/OfferInput";
import { DiagnosticReportView } from "@/components/DiagnosticReportView";
import { ErrorBanner } from "@/components/ErrorBanner";
import { toBannerContent, isSessionExpired, type BannerContent } from "@/lib/errors";
import { createDiagnostic } from "@/lib/api";
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
    <main className="mx-auto max-w-2xl px-6 py-10">
      <h1 className="text-xl font-bold text-slate-900">Analyser un CV</h1>
      <p className="mt-1 text-sm text-slate-600">
        Uploadez votre CV et l&apos;offre visée pour comprendre ce qui bloque côté ATS.
      </p>

      <div className="mt-6 flex flex-col gap-4">
        <CVDropzone file={file} onFileSelected={setFile} />
        <OfferInput value={offer} onChange={setOffer} />
        {banner && <ErrorBanner content={banner} />}
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit || isSubmitting}
          className="rounded-md bg-blue-500 px-4 py-3 font-semibold text-white disabled:opacity-50"
        >
          {isSubmitting ? "Analyse en cours, ça prend quelques secondes..." : "Analyser mon CV"}
        </button>
      </div>

      {report && (
        <div className="mt-10">
          <DiagnosticReportView report={report} />
        </div>
      )}
    </main>
  );
}
