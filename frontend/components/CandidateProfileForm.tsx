"use client";

import type { CandidateProfileInput } from "@/lib/types";

export interface CandidateProfileFormValue {
  full_name: string;
  phone: string;
  address: string;
  linkedin_url: string;
  portfolio_url: string;
  work_authorization: string;
  salary_expectation: string;
}

export const EMPTY_CANDIDATE_PROFILE_FORM_VALUE: CandidateProfileFormValue = {
  full_name: "",
  phone: "",
  address: "",
  linkedin_url: "",
  portfolio_url: "",
  work_authorization: "",
  salary_expectation: "",
};

export function toCandidateProfileInput(value: CandidateProfileFormValue): CandidateProfileInput {
  return {
    full_name: value.full_name,
    phone: value.phone,
    address: value.address.trim() || null,
    linkedin_url: value.linkedin_url.trim() || null,
    portfolio_url: value.portfolio_url.trim() || null,
    work_authorization: value.work_authorization,
    salary_expectation: value.salary_expectation.trim() || null,
  };
}

interface CandidateProfileFormProps {
  value: CandidateProfileFormValue;
  onChange: (value: CandidateProfileFormValue) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
}

const FIELDS: Array<{ key: keyof CandidateProfileFormValue; label: string; required?: boolean }> = [
  { key: "full_name", label: "Nom complet", required: true },
  { key: "phone", label: "Téléphone", required: true },
  { key: "address", label: "Adresse" },
  { key: "linkedin_url", label: "URL LinkedIn" },
  { key: "portfolio_url", label: "URL portfolio" },
  { key: "work_authorization", label: "Autorisation de travail", required: true },
  { key: "salary_expectation", label: "Prétentions salariales" },
];

export function CandidateProfileForm({ value, onChange, onSubmit, isSubmitting }: CandidateProfileFormProps) {
  return (
    <div className="flex flex-col gap-4 rounded-xl bg-white p-4 shadow-sm">
      {FIELDS.map(({ key, label, required }) => (
        <label key={key} className="flex flex-col gap-1 text-sm text-slate-700">
          {label}
          <input
            type="text"
            value={value[key]}
            required={required}
            onChange={(event) => onChange({ ...value, [key]: event.target.value })}
            className="rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
      ))}
      <button
        type="button"
        onClick={onSubmit}
        disabled={isSubmitting}
        className="w-fit rounded-md bg-blue-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        {isSubmitting ? "Enregistrement..." : "Enregistrer"}
      </button>
    </div>
  );
}
