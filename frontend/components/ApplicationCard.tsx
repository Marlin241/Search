"use client";

import { useState } from "react";
import { DiagnosticReportView } from "./DiagnosticReportView";
import { PersonalizedDocumentCard } from "./PersonalizedDocumentCard";
import { PrefilledFormReview } from "./PrefilledFormReview";
import { ErrorBanner } from "./ErrorBanner";
import { toBannerContent, type BannerContent } from "@/lib/errors";
import {
  generateCv,
  generateLetter,
  downloadCv,
  downloadLetter,
  getPrefilledForm,
  confirmApplication,
  markApplicationSentManually,
  ApiError,
} from "@/lib/api";
import type { Application, FormField } from "@/lib/types";

interface ApplicationCardProps {
  application: Application;
  token: string;
  onUpdated: (updated: Application) => void;
}

const STATUS_LABELS: Record<Application["status"], string> = {
  en_cours: "En attente de confirmation",
  soumise_auto: "Candidature envoyée automatiquement",
  a_soumettre_manuellement: "À envoyer manuellement",
  soumise_manuelle_confirmee: "Envoyée",
  echec_soumission: "Échec de l'envoi",
};

// Verbatim match to the detail string raised by POST /applications/{id}/confirm
// (backend/app/routers/applications.py) when the candidate's CV is flagged
// needs_review by the anti-hallucination check. Matched by exact message, not
// just status 422, since other 422s (e.g. missing fields) must fall through
// to the generic error banner instead of this dedicated block.
const NEEDS_REVIEW_DETAIL =
  "Ce CV contient des éléments à vérifier avant l'envoi automatique — relisez-le ou régénérez-le depuis le diagnostic.";

export function ApplicationCard({ application, token, onUpdated }: ApplicationCardProps) {
  const [banner, setBanner] = useState<BannerContent | null>(null);
  const [isLoadingForm, setIsLoadingForm] = useState(false);
  const [prefilledFields, setPrefilledFields] = useState<FormField[] | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const [needsReviewBlock, setNeedsReviewBlock] = useState<{ fields?: FormField[] } | null>(null);
  const [acknowledgedRisk, setAcknowledgedRisk] = useState(false);

  async function submitConfirm(fields: FormField[] | undefined, overrideNeedsReview: boolean) {
    setBanner(null);
    setIsConfirming(true);
    try {
      const updated = await confirmApplication(token, application.id, fields, overrideNeedsReview);
      setPrefilledFields(null);
      setNeedsReviewBlock(null);
      setAcknowledgedRisk(false);
      onUpdated(updated);
    } catch (error) {
      if (error instanceof ApiError && error.status === 422 && error.message === NEEDS_REVIEW_DETAIL) {
        setNeedsReviewBlock({ fields });
        setAcknowledgedRisk(false);
      } else {
        setBanner(toBannerContent(error));
      }
    } finally {
      setIsConfirming(false);
    }
  }

  async function handleConfirmClick() {
    setBanner(null);
    if (application.ats_type === null) {
      await submitConfirm(undefined, false);
      return;
    }

    setIsLoadingForm(true);
    try {
      const form = await getPrefilledForm(token, application.id);
      setPrefilledFields(form.fields);
    } catch (error) {
      setBanner(toBannerContent(error));
    } finally {
      setIsLoadingForm(false);
    }
  }

  async function handleReviewConfirm(fields: FormField[]) {
    await submitConfirm(fields, false);
  }

  function handleCancelNeedsReview() {
    setNeedsReviewBlock(null);
    setAcknowledgedRisk(false);
  }

  async function handleSendAnyway() {
    await submitConfirm(needsReviewBlock?.fields, true);
  }

  async function handleMarkSent() {
    setBanner(null);
    try {
      const updated = await markApplicationSentManually(token, application.id);
      onUpdated(updated);
    } catch (error) {
      setBanner(toBannerContent(error));
    }
  }

  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-900">{application.job_title}</p>
          <p className="text-sm text-slate-600">{application.company_name}</p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
          {STATUS_LABELS[application.status]}
        </span>
      </div>

      {banner && (
        <div className="mt-3">
          <ErrorBanner content={banner} />
        </div>
      )}
      {application.error_message && (
        <p className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {application.error_message}
        </p>
      )}

      <div className="mt-4">
        <DiagnosticReportView report={application.diagnostic} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <PersonalizedDocumentCard
          title="CV optimisé"
          generatedLabel="Générer CV optimisé"
          onGenerate={() => generateCv(token, application.diagnostic_id)}
          onDownload={() => downloadCv(token, application.diagnostic_id)}
          downloadFilename="cv_optimise.pdf"
        />
        <PersonalizedDocumentCard
          title="Lettre de motivation"
          generatedLabel="Générer lettre de motivation"
          onGenerate={() => generateLetter(token, application.diagnostic_id)}
          onDownload={() => downloadLetter(token, application.diagnostic_id)}
          downloadFilename="lettre_motivation.pdf"
        />
      </div>

      {needsReviewBlock && (
        <div className="mt-4 rounded-md border border-orange-300 bg-orange-50 px-3 py-3 text-sm text-orange-800">
          <p>{NEEDS_REVIEW_DETAIL}</p>
          <label className="mt-3 flex items-start gap-2">
            <input
              type="checkbox"
              checked={acknowledgedRisk}
              onChange={(event) => setAcknowledgedRisk(event.target.checked)}
              className="mt-0.5"
            />
            <span>Je comprends le risque et je souhaite envoyer la candidature malgré tout.</span>
          </label>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={handleSendAnyway}
              disabled={!acknowledgedRisk || isConfirming}
              className="rounded-md bg-orange-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {isConfirming ? "Envoi en cours..." : "Envoyer quand même"}
            </button>
            <button
              type="button"
              onClick={handleCancelNeedsReview}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
            >
              Annuler
            </button>
          </div>
        </div>
      )}

      {!needsReviewBlock && application.status === "en_cours" && !prefilledFields && (
        <button
          type="button"
          onClick={handleConfirmClick}
          disabled={isLoadingForm}
          className="mt-4 rounded-md bg-blue-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {isLoadingForm ? "Préparation du formulaire..." : "Confirmer la candidature"}
        </button>
      )}

      {!needsReviewBlock && prefilledFields && (
        <div className="mt-4">
          <PrefilledFormReview
            fields={prefilledFields}
            onConfirm={handleReviewConfirm}
            onCancel={() => setPrefilledFields(null)}
            isConfirming={isConfirming}
          />
        </div>
      )}

      {application.status === "a_soumettre_manuellement" && (
        <div className="mt-4 flex flex-col gap-2">
          <a
            href={application.offer_url}
            target="_blank"
            rel="noreferrer"
            className="w-fit text-sm font-semibold text-blue-600 underline"
          >
            Ouvrir la page de candidature
          </a>
          <button
            type="button"
            onClick={handleMarkSent}
            className="w-fit rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
          >
            Marquer comme envoyée
          </button>
        </div>
      )}
    </div>
  );
}
