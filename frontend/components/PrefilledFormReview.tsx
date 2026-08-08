"use client";

import { useState } from "react";
import type { FormField } from "@/lib/types";

interface PrefilledFormReviewProps {
  fields: FormField[];
  onConfirm: (fields: FormField[]) => void;
  onCancel: () => void;
  isConfirming: boolean;
}

export function PrefilledFormReview({ fields, onConfirm, onCancel, isConfirming }: PrefilledFormReviewProps) {
  const [values, setValues] = useState<FormField[]>(fields);

  function updateValue(name: string, newValue: string) {
    setValues((prev) => prev.map((field) => (field.name === name ? { ...field, value: newValue } : field)));
  }

  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
      <p className="text-sm font-semibold text-slate-900">Relisez et complétez le formulaire avant l&apos;envoi</p>
      <div className="mt-3 flex flex-col gap-3">
        {values.map((field) => (
          <label key={field.name} className="flex flex-col gap-1 text-sm text-slate-700">
            <span>
              {field.label}
              {field.is_custom && <span className="ml-2 text-xs text-blue-600">(généré par l&apos;IA — à vérifier)</span>}
            </span>
            {field.field_type === "textarea" ? (
              <textarea
                value={field.value ?? ""}
                onChange={(event) => updateValue(field.name, event.target.value)}
                rows={3}
                className="rounded-md border border-slate-300 px-3 py-2"
              />
            ) : (
              <input
                type="text"
                value={field.value ?? ""}
                onChange={(event) => updateValue(field.name, event.target.value)}
                className="rounded-md border border-slate-300 px-3 py-2"
              />
            )}
          </label>
        ))}
      </div>
      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={() => onConfirm(values)}
          disabled={isConfirming}
          className="rounded-md bg-blue-500 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {isConfirming ? "Envoi en cours..." : "Envoyer la candidature"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
        >
          Annuler
        </button>
      </div>
    </div>
  );
}
