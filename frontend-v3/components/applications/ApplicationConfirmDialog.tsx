"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, Send } from "lucide-react";
import { confirmApplication, getPrefilledForm } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Skeleton } from "@/components/ui/Skeleton";
import { PrefilledFormFields } from "@/components/applications/PrefilledFormFields";
import { ApiError } from "@/lib/types";
import type { ApplicationOut, FormField } from "@/lib/types";

// Verbatim match to the detail string raised by POST /applications/{id}/confirm
// (backend/app/routers/applications.py) when the candidate's CV is flagged
// needs_review by the anti-hallucination check. Matched by exact message,
// not just status 422, since other 422s (e.g. missing profile fields) must
// fall through to the generic error banner instead of this dedicated gate.
const NEEDS_REVIEW_DETAIL =
  "Ce CV contient des éléments à vérifier avant l'envoi automatique — relisez-le ou régénérez-le depuis le diagnostic.";

export function ApplicationConfirmDialog({
  application,
  token,
  isOpen,
  onClose,
  onConfirmed,
}: {
  application: ApplicationOut;
  token: string;
  isOpen: boolean;
  onClose: () => void;
  onConfirmed: (updated: ApplicationOut) => void;
}) {
  const [isLoadingForm, setIsLoadingForm] = useState(false);
  const [fields, setFields] = useState<FormField[] | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsReviewGate, setNeedsReviewGate] = useState(false);
  const [acknowledgedRisk, setAcknowledgedRisk] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setError(null);
    setNeedsReviewGate(false);
    setAcknowledgedRisk(false);
    setFields(null);

    if (application.ats_type === null) return;

    setIsLoadingForm(true);
    getPrefilledForm(token, application.id)
      .then((form) => setFields(form.fields))
      .catch((err) => setError(err?.detail || "Impossible de charger le formulaire."))
      .finally(() => setIsLoadingForm(false));
  }, [isOpen, application.ats_type, application.id, token]);

  const updateField = (name: string, value: string) => {
    setFields((prev) =>
      prev ? prev.map((f) => (f.name === name ? { ...f, value } : f)) : prev
    );
  };

  const submit = async (overrideNeedsReview: boolean) => {
    setError(null);
    setIsConfirming(true);
    try {
      const updated = await confirmApplication(token, application.id, {
        fields: fields ?? undefined,
        override_needs_review: overrideNeedsReview,
      });
      toast.success("Candidature confirmée.");
      onConfirmed(updated);
      onClose();
    } catch (err) {
      if (
        err instanceof ApiError &&
        err.status === 422 &&
        err.detail === NEEDS_REVIEW_DETAIL
      ) {
        setNeedsReviewGate(true);
        setAcknowledgedRisk(false);
      } else {
        const message = err instanceof ApiError ? err.detail : "La confirmation a échoué.";
        setError(message);
        toast.error(message);
      }
    } finally {
      setIsConfirming(false);
    }
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Confirmer la candidature"
      description={
        application.ats_type === null
          ? "Cette offre ne peut pas être envoyée automatiquement — elle sera marquée à envoyer manuellement."
          : "Relisez et complétez le formulaire avant l'envoi automatique."
      }
      className="max-w-lg w-full"
    >
      <div className="space-y-4 mt-2">
        {error && (
          <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-xl text-destructive text-xs font-semibold flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}

        {isLoadingForm && (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        )}

        {!isLoadingForm && fields && fields.length > 0 && (
          <PrefilledFormFields fields={fields} onChange={updateField} />
        )}

        {needsReviewGate && (
          <div className="p-3 bg-warning/10 border border-warning/30 rounded-xl space-y-2">
            <p className="text-xs font-semibold text-warning-dark flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              Le CV généré contient des éléments à vérifier avant un envoi automatique.
            </p>
            <label className="flex items-start gap-2 text-xs text-foreground/90">
              <input
                type="checkbox"
                checked={acknowledgedRisk}
                onChange={(e) => setAcknowledgedRisk(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-input text-primary focus:ring-primary shrink-0 cursor-pointer"
              />
              J&apos;ai relu ce CV et je confirme l&apos;envoi malgré cet avertissement.
            </label>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Annuler
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon={<Send className="w-4 h-4" />}
            isLoading={isConfirming}
            disabled={isLoadingForm || (needsReviewGate && !acknowledgedRisk)}
            onClick={() => submit(needsReviewGate)}
          >
            {needsReviewGate ? "Confirmer quand même" : "Confirmer et envoyer"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
