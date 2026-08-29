"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export const INTERVIEW_PERSONAS = [
  {
    value: "recruteur_rh",
    label: "Recruteur RH",
    description: "Premier échange centré sur le parcours, la motivation et le savoir-être.",
  },
  {
    value: "manager_technique",
    label: "Manager technique",
    description: "Évalue la compétence métier et la mise en pratique concrète.",
  },
  {
    value: "direction",
    label: "Direction",
    description: "Vision stratégique, autonomie et adéquation avec les enjeux du poste.",
  },
  {
    value: "pair_futur_collegue",
    label: "Futur collègue",
    description: "Échange informel sur le quotidien de l'équipe et la collaboration.",
  },
] as const;

export function PersonaCards({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {INTERVIEW_PERSONAS.map((persona) => {
        const selected = value === persona.value;
        return (
          <button
            key={persona.value}
            type="button"
            onClick={() => onChange(persona.value)}
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
            <p className="text-sm font-bold text-foreground">{persona.label}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{persona.description}</p>
          </button>
        );
      })}
    </div>
  );
}
