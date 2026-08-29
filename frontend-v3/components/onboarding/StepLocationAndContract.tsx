"use client";

import { TagInput } from "./TagInput";
import { SalarySlider } from "./SalarySlider";
import { cn } from "@/lib/utils";
import { useCityList } from "@/lib/useCityList";

const CONTRACT_TYPES = [
  { value: "CDI", label: "CDI" },
  { value: "CDD", label: "CDD" },
  { value: "Alternance", label: "Alternance" },
  { value: "Stage", label: "Stage" },
  { value: "Freelance", label: "Freelance" },
];

export interface StepLocationAndContractProps {
  desiredLocations: string[];
  onDesiredLocationsChange: (values: string[]) => void;
  remotePreference: boolean;
  onRemotePreferenceChange: (value: boolean) => void;
  contractTypes: string[];
  onContractTypesChange: (values: string[]) => void;
  salaryMin: number;
  salaryMax: number;
  onSalaryChange: (min: number, max: number) => void;
}

export function StepLocationAndContract({
  desiredLocations,
  onDesiredLocationsChange,
  remotePreference,
  onRemotePreferenceChange,
  contractTypes,
  onContractTypesChange,
  salaryMin,
  salaryMax,
  onSalaryChange,
}: StepLocationAndContractProps) {
  const cities = useCityList();

  const toggleContractType = (value: string) => {
    if (contractTypes.includes(value)) {
      onContractTypesChange(contractTypes.filter((c) => c !== value));
    } else {
      onContractTypesChange([...contractTypes, value]);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-bold text-foreground">
          Où et pour quel salaire ?
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Choisis une ou plusieurs communes. Le ranking étend automatiquement
          au département et à la région.
        </p>
      </div>

      <TagInput
        label="Localisation"
        values={desiredLocations}
        onChange={onDesiredLocationsChange}
        placeholder="ex : Dakar, Abidjan, Paris..."
        suggestions={cities}
        hint="Ajoute autant de villes que tu veux."
      />

      <label className="flex items-center justify-between rounded-xl border border-border px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-foreground">
            Ouvert(e) au télétravail
          </p>
          <p className="text-xs text-muted-foreground">
            Partiel ou total, on élargit la recherche en conséquence.
          </p>
        </div>
        <input
          type="checkbox"
          checked={remotePreference}
          onChange={(e) => onRemotePreferenceChange(e.target.checked)}
          className="h-5 w-9 shrink-0 cursor-pointer appearance-none rounded-full bg-muted transition-colors checked:bg-primary relative after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-transform checked:after:translate-x-4"
        />
      </label>

      <div className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Type de contrat
        </label>
        <div className="flex flex-wrap gap-2">
          {CONTRACT_TYPES.map((type) => {
            const selected = contractTypes.includes(type.value);
            return (
              <button
                key={type.value}
                type="button"
                onClick={() => toggleContractType(type.value)}
                className={cn(
                  "rounded-full border px-4 py-1.5 text-xs font-semibold transition-all",
                  selected
                    ? "border-primary bg-primary text-white"
                    : "border-border text-muted-foreground hover:border-primary/40"
                )}
              >
                {type.label}
              </button>
            );
          })}
        </div>
      </div>

      <SalarySlider
        min={18000}
        max={100000}
        step={1000}
        valueMin={salaryMin}
        valueMax={salaryMax}
        onChange={onSalaryChange}
      />
    </div>
  );
}
