"use client";

import { useState } from "react";
import { Button } from "./ui/Button";
import { Input, Select, Textarea } from "./ui/Field";
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
    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950">
      <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">
        Relisez et complétez le formulaire avant l&apos;envoi
      </p>
      <div className="mt-3 flex flex-col gap-3">
        {values.map((field) => {
          const needsCompletion = field.required && !field.value;
          return (
            <label key={field.name} className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-300">
              <span>
                {field.label}
                {field.is_custom && (
                  <span className="ml-2 text-xs text-amber-700 dark:text-amber-400">
                    (généré par l&apos;IA — à vérifier)
                  </span>
                )}
                {needsCompletion && (
                  <span className="ml-2 text-xs font-semibold text-red-600 dark:text-red-400">(à compléter)</span>
                )}
              </span>
              {field.field_type === "textarea" ? (
                <Textarea
                  value={field.value ?? ""}
                  onChange={(event) => updateValue(field.name, event.target.value)}
                  rows={3}
                />
              ) : field.field_type === "select" ? (
                <Select value={field.value ?? ""} onChange={(event) => updateValue(field.name, event.target.value)}>
                  <option value="" disabled hidden>
                    Sélectionnez…
                  </option>
                  {(field.options ?? []).map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </Select>
              ) : (
                <Input
                  type="text"
                  value={field.value ?? ""}
                  onChange={(event) => updateValue(field.name, event.target.value)}
                />
              )}
            </label>
          );
        })}
      </div>
      <div className="mt-4 flex gap-2">
        <Button onClick={() => onConfirm(values)} isLoading={isConfirming} size="sm">
          {isConfirming ? "Envoi en cours..." : "Envoyer la candidature"}
        </Button>
        <Button onClick={onCancel} variant="secondary" size="sm">
          Annuler
        </Button>
      </div>
    </div>
  );
}
