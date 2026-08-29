"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { Dialog } from "@/components/ui/Dialog";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { getCompatibilityDetail } from "@/lib/api";
import { cn, scoreColor, sourceLabel } from "@/lib/utils";
import type { CompatibilityDetailOut, JobListing } from "@/lib/types";
import { ApiError } from "@/lib/types";

const BREAKDOWN_LABELS: { key: keyof CompatibilityDetailOut["breakdown"]; label: string }[] = [
  { key: "title", label: "Intitulé de poste" },
  { key: "location", label: "Localisation" },
  { key: "seniority", label: "Expérience" },
  { key: "salary", label: "Salaire" },
  { key: "freshness", label: "Fraîcheur de l'offre" },
];

export interface CompatibilityDetailModalProps {
  listing: JobListing | null;
  token: string | null;
  onClose: () => void;
}

export function CompatibilityDetailModal({
  listing,
  token,
  onClose,
}: CompatibilityDetailModalProps) {
  const [detail, setDetail] = useState<CompatibilityDetailOut | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!listing || !token) {
      setDetail(null);
      setError(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    getCompatibilityDetail(token, listing)
      .then(setDetail)
      .catch((err: unknown) => {
        const detail =
          err instanceof ApiError
            ? err.detail
            : "Impossible d'obtenir le détail de compatibilité pour le moment.";
        setError(detail);
      })
      .finally(() => setIsLoading(false));
  }, [listing, token]);

  return (
    <Dialog
      isOpen={!!listing}
      onClose={onClose}
      title="Détail de compatibilité"
      description={
        listing ? `${listing.title} · ${sourceLabel(listing.source)}` : undefined
      }
      className="max-w-lg"
    >
      <div className="mt-2 space-y-5">
        {isLoading && (
          <div className="flex flex-col items-center gap-2 py-10 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
            <span className="text-xs font-medium">Analyse en cours...</span>
          </div>
        )}

        {!isLoading && error && (
          <div className="flex items-start gap-2.5 rounded-xl border border-warning/30 bg-warning/10 p-3.5 text-xs text-warning-dark">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!isLoading && detail && listing && (
          <>
            <div className="flex items-center justify-center">
              <ScoreRing score={listing.compatibility_score} size="lg" label="Score global" />
            </div>

            <p className="text-center text-xs text-muted-foreground">
              Les pourcentages reflètent vos critères de recherche ; le résumé
              et les points ci-dessous s&apos;appuient en plus sur le contenu
              de votre CV.
            </p>

            <div className="space-y-2.5">
              {BREAKDOWN_LABELS.map(({ key, label }) => {
                const value = detail.breakdown[key];
                return (
                  <div key={key} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-muted-foreground">{label}</span>
                      <span className={cn("font-bold", scoreColor(value))}>{value}%</span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted/50">
                      <div
                        className={cn(
                          "h-full rounded-full transition-all",
                          value >= 70
                            ? "bg-success"
                            : value >= 40
                              ? "bg-warning"
                              : "bg-destructive"
                        )}
                        style={{ width: `${value}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="rounded-xl border border-border bg-muted/30 p-3.5 text-xs leading-relaxed text-foreground">
              {detail.summary}
            </div>

            {detail.strengths.length > 0 && (
              <div className="space-y-1.5">
                <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Points forts
                </h4>
                <ul className="space-y-1.5">
                  {detail.strengths.map((strength, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-foreground">
                      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
                      <span>{strength}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {detail.concerns.length > 0 && (
              <div className="space-y-1.5">
                <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Points de vigilance
                </h4>
                <ul className="space-y-1.5">
                  {detail.concerns.map((concern, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-foreground">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
                      <span>{concern}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </Dialog>
  );
}
