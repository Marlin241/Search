"use client";

import { Card } from "./ui/Card";

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
    <Card className="p-1.5">
      <div className="flex gap-1 px-2 pt-2">
        <button
          type="button"
          onClick={() => onChange({ ...value, mode: "text" })}
          className={`rounded-xl px-4 py-2 text-sm font-bold ${
            value.mode === "text" ? "text-accent-strong" : "text-ink-faint"
          }`}
        >
          Coller le texte
        </button>
        <button
          type="button"
          onClick={() => onChange({ ...value, mode: "url" })}
          className={`rounded-xl px-4 py-2 text-sm font-bold ${
            value.mode === "url" ? "text-accent-strong" : "text-ink-faint"
          }`}
        >
          URL de l&apos;offre
        </button>
      </div>
      {value.mode === "text" ? (
        <textarea
          value={value.text}
          onChange={(event) => onChange({ ...value, text: event.target.value })}
          rows={5}
          placeholder="Collez ici le texte de l'offre d'emploi"
          className="w-full resize-none rounded-2xl border-0 bg-transparent px-4 py-3 text-sm text-ink placeholder:text-ink-faint focus:outline-none"
        />
      ) : (
        <input
          type="url"
          value={value.url}
          onChange={(event) => onChange({ ...value, url: event.target.value })}
          placeholder="https://..."
          className="w-full rounded-2xl border-0 bg-transparent px-4 py-3 text-sm text-ink placeholder:text-ink-faint focus:outline-none"
        />
      )}
    </Card>
  );
}
