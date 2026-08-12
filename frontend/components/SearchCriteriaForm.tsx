"use client";

import { Card } from "./ui/Card";
import { Button } from "./ui/Button";
import { Input } from "./ui/Field";
import type { SearchCriteria } from "@/lib/types";

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
    <Card className="flex flex-col gap-4 p-4">
      <label className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-300">
        Mots-clés
        <Input
          type="text"
          value={value.keywords}
          onChange={(event) => onChange({ ...value, keywords: event.target.value })}
          placeholder="ex: développeur python"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-300">
        Localisation
        <Input
          type="text"
          value={value.location}
          onChange={(event) => onChange({ ...value, location: event.target.value })}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-300">
        Type de contrat
        <Input
          type="text"
          value={value.contractType}
          onChange={(event) => onChange({ ...value, contractType: event.target.value })}
          placeholder="ex: CDI"
        />
      </label>
      <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
        <input
          type="checkbox"
          checked={value.remote}
          onChange={(event) => onChange({ ...value, remote: event.target.checked })}
          className="h-4 w-4 rounded border-slate-300 text-amber-600 focus:ring-amber-500 dark:border-ink-800"
        />
        Télétravail uniquement
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-300">
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
