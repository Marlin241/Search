"use client";

import { Card } from "./ui/Card";
import { Button } from "./ui/Button";
import { Input, Select } from "./ui/Field";
import type { SearchCriteria } from "@/lib/types";

const CONTRACT_TYPES = [
  { value: "", label: "Tous types de contrat" },
  { value: "cdi", label: "CDI" },
  { value: "cdd", label: "CDD" },
  { value: "alternance", label: "Alternance" },
  { value: "stage", label: "Stage" },
  { value: "interim", label: "Intérim" },
  { value: "freelance", label: "Freelance / Indépendant" },
];

export interface SearchCriteriaFormValue {
  keywords: string;
  location: string;
  contractType: string;
  remote: boolean;
  excludeKeywords: string;
}

export const EMPTY_SEARCH_CRITERIA_FORM_VALUE: SearchCriteriaFormValue = {
  keywords: "",
  location: "",
  contractType: "",
  remote: false,
  excludeKeywords: "",
};

function splitCommaList(raw: string): string[] {
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

export function toSearchCriteria(value: SearchCriteriaFormValue): SearchCriteria {
  return {
    keywords: value.keywords,
    location: value.location.trim() || undefined,
    contract_type: value.contractType.trim() || undefined,
    remote: value.remote || undefined,
    exclude_keywords: splitCommaList(value.excludeKeywords),
  };
}

interface SearchCriteriaFormProps {
  value: SearchCriteriaFormValue;
  onChange: (value: SearchCriteriaFormValue) => void;
  onSearch: () => void;
  isSearching: boolean;
}

export function SearchCriteriaForm({ value, onChange, onSearch, isSearching }: SearchCriteriaFormProps) {
  return (
    <Card className="flex flex-col gap-3.5 p-5">
      <label className="flex flex-col gap-1.5 text-[13px] font-semibold text-ink-soft">
        Mots-clés
        <Input
          type="text"
          value={value.keywords}
          onChange={(event) => onChange({ ...value, keywords: event.target.value })}
          placeholder="ex: développeur python"
        />
      </label>
      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5 text-[13px] font-semibold text-ink-soft">
          Localisation
          <Input
            type="text"
            value={value.location}
            onChange={(event) => onChange({ ...value, location: event.target.value })}
          />
        </label>
        <label className="flex flex-col gap-1.5 text-[13px] font-semibold text-ink-soft">
          Type de contrat
          <Select
            value={value.contractType}
            onChange={(event) => onChange({ ...value, contractType: event.target.value })}
          >
            {CONTRACT_TYPES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </label>
      </div>
      <label className="flex items-center gap-2.5 text-sm font-semibold text-ink-soft">
        <input
          type="checkbox"
          checked={value.remote}
          onChange={(event) => onChange({ ...value, remote: event.target.checked })}
          className="h-[18px] w-[18px] rounded-[6px] border-border-strong text-accent-strong focus:ring-accent"
        />
        Télétravail uniquement
      </label>
      <label className="flex flex-col gap-1.5 text-[13px] font-semibold text-ink-soft">
        Mots-clés à exclure (séparés par des virgules)
        <Input
          type="text"
          value={value.excludeKeywords}
          onChange={(event) => onChange({ ...value, excludeKeywords: event.target.value })}
        />
      </label>
      <Button onClick={onSearch} disabled={value.keywords.trim().length === 0} isLoading={isSearching} className="w-fit">
        {isSearching ? "Recherche en cours..." : "Rechercher"}
      </Button>
    </Card>
  );
}
