"use client";

import { Sparkles } from "lucide-react";

export interface StepConfirmProps {
  firstName: string;
  lastName: string;
  desiredJobTitles: string[];
  desiredLocations: string[];
  remotePreference: boolean;
  contractTypes: string[];
  salaryMin: number;
  salaryMax: number;
  salaryCurrency: string;
  weeklyGoal: number;
  cvFileName: string | null;
}

export function StepConfirm({
  firstName,
  lastName,
  desiredJobTitles,
  desiredLocations,
  remotePreference,
  contractTypes,
  salaryMin,
  salaryMax,
  salaryCurrency,
  weeklyGoal,
  cvFileName,
}: StepConfirmProps) {
  const rows: { label: string; value: string }[] = [
    { label: "Nom", value: `${firstName} ${lastName}`.trim() || "—" },
    { label: "Métiers", value: desiredJobTitles.join(", ") || "—" },
    {
      label: "Localisation",
      value:
        [desiredLocations.join(", "), remotePreference ? "télétravail ok" : null]
          .filter(Boolean)
          .join(" · ") || "—",
    },
    { label: "Contrats", value: contractTypes.join(", ") || "—" },
    {
      label: "Salaire visé",
      value: `${salaryMin.toLocaleString("fr-FR")} - ${salaryMax.toLocaleString("fr-FR")} ${salaryCurrency} / mois`,
    },
    { label: "Objectif hebdo", value: `${weeklyGoal} candidature${weeklyGoal > 1 ? "s" : ""}` },
    { label: "CV de référence", value: cvFileName ?? "Non fourni" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Sparkles className="h-5 w-5" />
        </div>
        <div>
          <h2 className="font-display text-2xl font-bold text-foreground">
            C'est prêt !
          </h2>
          <p className="text-sm text-muted-foreground">
            Vérifie ton profil avant de découvrir tes premières offres.
          </p>
        </div>
      </div>

      <div className="divide-y divide-border rounded-xl border border-border">
        {rows.map((row) => (
          <div key={row.label} className="flex items-start justify-between gap-4 px-4 py-3">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {row.label}
            </span>
            <span className="text-right text-sm font-medium text-foreground">
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
