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
    <div className="rounded-3xl bg-accent-soft p-5">
      <p className="text-sm font-bold text-accent-ink">Relisez et complétez le formulaire avant l&apos;envoi</p>
      <div className="mt-3.5 flex flex-col gap-3">
        {values.map((field) => {
          const needsCompletion = field.required && !field.value;
          return (
            <label key={field.name} className="flex flex-col gap-1.5 text-[13px] font-semibold text-accent-ink">
              <span>
                {field.label}
                {field.is_custom && <span className="ml-2 text-xs font-normal opacity-80">(généré par l&apos;IA — à vérifier)</span>}
                {needsCompletion && (
                  <span className="ml-2 text-xs font-bold text-attention-ink">(à compléter)</span>
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
