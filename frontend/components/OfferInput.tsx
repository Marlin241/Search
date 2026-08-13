"use client";

import { Card } from "./ui/Card";
import { Input, Textarea } from "./ui/Field";

export interface OfferInputValue {
  mode: "text" | "url";
  text: string;
  url: string;
}

export const EMPTY_OFFER_VALUE: OfferInputValue = { mode: "text", text: "", url: "" };

interface OfferInputProps {
  value: OfferInputValue;
  onChange: (value: OfferInputValue) => void;
}

export function OfferInput({ value, onChange }: OfferInputProps) {
  return (
    <Card className="p-4">
      <div className="mb-3 flex gap-1 border-b border-slate-200 dark:border-ink-800">
        <button
          type="button"
          onClick={() => onChange({ ...value, mode: "text" })}
          className={`px-4 py-2 text-sm font-semibold ${
            value.mode === "text"
              ? "border-b-2 border-amber-500 text-amber-700 dark:border-amber-400 dark:text-amber-400"
              : "text-slate-500 dark:text-slate-400"
          }`}
        >
          Coller le texte
        </button>
        <button
          type="button"
          onClick={() => onChange({ ...value, mode: "url" })}
          className={`px-4 py-2 text-sm font-semibold ${
            value.mode === "url"
              ? "border-b-2 border-amber-500 text-amber-700 dark:border-amber-400 dark:text-amber-400"
              : "text-slate-500 dark:text-slate-400"
          }`}
        >
          URL de l&apos;offre
        </button>
      </div>
      {value.mode === "text" ? (
        <Textarea
          value={value.text}
          onChange={(event) => onChange({ ...value, text: event.target.value })}
          rows={5}
          placeholder="Collez ici le texte de l'offre d'emploi"
          className="w-full"
        />
      ) : (
        <Input
          type="url"
          value={value.url}
          onChange={(event) => onChange({ ...value, url: event.target.value })}
          placeholder="https://..."
          className="w-full"
        />
      )}
    </Card>
  );
}
