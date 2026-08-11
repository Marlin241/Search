"use client";

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
    <div className="flex flex-col gap-4 rounded-xl bg-white p-4 shadow-sm">
      <label className="flex flex-col gap-1 text-sm text-slate-700">
        Mots-clés
        <input
          type="text"
          value={value.keywords}
          onChange={(event) => onChange({ ...value, keywords: event.target.value })}
          placeholder="ex: développeur python"
          className="rounded-md border border-slate-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-700">
        Localisation
        <input
          type="text"
          value={value.location}
          onChange={(event) => onChange({ ...value, location: event.target.value })}
          className="rounded-md border border-slate-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-700">
        Type de contrat
        <input
          type="text"
          value={value.contractType}
          onChange={(event) => onChange({ ...value, contractType: event.target.value })}
          placeholder="ex: CDI"
          className="rounded-md border border-slate-300 px-3 py-2"
        />
      </label>
      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={value.remote}
          onChange={(event) => onChange({ ...value, remote: event.target.checked })}
        />
        Télétravail uniquement
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-700">
        Mots-clés à exclure (séparés par des virgules)
        <input
          type="text"
          value={value.excludeKeywords}
          onChange={(event) => onChange({ ...value, excludeKeywords: event.target.value })}
          className="rounded-md border border-slate-300 px-3 py-2"
        />
      </label>
      <button
        type="button"
        onClick={onSearch}
        disabled={isSearching || value.keywords.trim().length === 0}
        className="w-fit rounded-md bg-blue-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        {isSearching ? "Recherche en cours..." : "Rechercher"}
      </button>
    </div>
  );
}
