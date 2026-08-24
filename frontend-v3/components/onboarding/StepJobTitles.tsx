"use client";

import { Check } from "lucide-react";
import { TagInput } from "./TagInput";
import { cn } from "@/lib/utils";

const JOB_TITLE_SUGGESTIONS = [
  "Développeur(se) full stack",
  "Développeur(se) backend",
  "Développeur(se) frontend",
  "Ingénieur(e) logiciel",
  "Data engineer",
  "Data analyst",
  "Data scientist",
  "Chef(fe) de projet",
  "Product manager",
  "Product owner",
  "UX/UI designer",
  "DevOps engineer",
  "Ingénieur(e) big data",
  "Administrateur(trice) systèmes",
  "Consultant(e) IT",
  "Chargé(e) de recrutement",
  "Commercial(e)",
  "Business developer",
  "Comptable",
  "Contrôleur(se) de gestion",
];

const SENIORITY_LEVELS = [
  { value: "junior", label: "Débutant", description: "0-1 an d'expérience" },
  { value: "confirme", label: "Junior", description: "1-3 ans d'expérience" },
  { value: "confirme_plus", label: "Confirmé", description: "3-6 ans d'expérience" },
  { value: "senior", label: "Senior", description: "6 ans et plus" },
];

export interface StepJobTitlesProps {
  desiredJobTitles: string[];
  onDesiredJobTitlesChange: (values: string[]) => void;
  seniorityLevel: string | null;
  onSeniorityLevelChange: (value: string) => void;
}

export function StepJobTitles({
  desiredJobTitles,
  onDesiredJobTitlesChange,
  seniorityLevel,
  onSeniorityLevelChange,
}: StepJobTitlesProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-bold text-foreground">
          Quels métiers recherches-tu ?
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Ajoute un ou plusieurs intitulés de poste. Ça nous aide à te
          proposer les offres les plus pertinentes.
        </p>
      </div>

      <TagInput
        label="Métiers recherchés"
        values={desiredJobTitles}
        onChange={onDesiredJobTitlesChange}
        placeholder="ex : Développeur backend..."
        suggestions={JOB_TITLE_SUGGESTIONS}
        hint="Appuie sur Entrée ou virgule pour valider un intitulé."
      />

      <div className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Niveau d'expérience
        </label>
        <div className="grid grid-cols-2 gap-3">
          {SENIORITY_LEVELS.map((level) => {
            const selected = seniorityLevel === level.value;
            return (
              <button
                key={level.value}
                type="button"
                onClick={() => onSeniorityLevelChange(level.value)}
                className={cn(
                  "relative rounded-xl border p-4 text-left transition-all",
                  selected
                    ? "border-primary bg-primary/5 ring-2 ring-primary/30"
                    : "border-border hover:border-primary/40"
                )}
              >
                {selected && (
                  <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-white">
                    <Check className="h-3 w-3" />
                  </span>
                )}
                <p className="text-sm font-bold text-foreground">{level.label}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {level.description}
                </p>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
