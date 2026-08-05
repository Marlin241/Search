"use client";

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
    <div className="rounded-xl bg-white p-4">
      <div className="mb-3 flex gap-1 border-b border-slate-200">
        <button
          type="button"
          onClick={() => onChange({ ...value, mode: "text" })}
          className={`px-4 py-2 text-sm font-semibold ${
            value.mode === "text" ? "border-b-2 border-blue-500 text-blue-600" : "text-slate-500"
          }`}
        >
          Coller le texte
        </button>
        <button
          type="button"
          onClick={() => onChange({ ...value, mode: "url" })}
          className={`px-4 py-2 text-sm font-semibold ${
            value.mode === "url" ? "border-b-2 border-blue-500 text-blue-600" : "text-slate-500"
          }`}
        >
          URL de l'offre
        </button>
      </div>
      {value.mode === "text" ? (
        <textarea
          value={value.text}
          onChange={(event) => onChange({ ...value, text: event.target.value })}
          rows={5}
          placeholder="Collez ici le texte de l'offre d'emploi"
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      ) : (
        <input
          type="url"
          value={value.url}
          onChange={(event) => onChange({ ...value, url: event.target.value })}
          placeholder="https://..."
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      )}
    </div>
  );
}
