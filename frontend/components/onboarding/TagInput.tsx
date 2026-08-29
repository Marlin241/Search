"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

// Accent-insensitive match, mirrors the backend's
// app.job_search.keyword_matching convention (French users commonly type
// without accents - "developpeur" should still surface "Développeur").
function normalize(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

export interface TagInputProps {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  suggestions?: string[];
  hint?: string;
}

export function TagInput({
  label,
  values,
  onChange,
  placeholder,
  suggestions,
  hint,
}: TagInputProps) {
  const [draft, setDraft] = useState("");

  const filteredSuggestions =
    suggestions && draft.trim().length > 0
      ? suggestions
          .filter((s) => {
            const normalizedDraft = normalize(draft.trim());
            const normalizedSuggestion = normalize(s);
            return (
              !values.includes(s) &&
              (normalizedSuggestion.startsWith(normalizedDraft) ||
                normalizedSuggestion.includes(` ${normalizedDraft}`))
            );
          })
          .sort((a, b) => {
            // Prefix matches first, substring matches after - "Develo"
            // should rank "Développeur..." above "Business developer".
            const normalizedDraft = normalize(draft.trim());
            const aStarts = normalize(a).startsWith(normalizedDraft);
            const bStarts = normalize(b).startsWith(normalizedDraft);
            if (aStarts === bStarts) return 0;
            return aStarts ? -1 : 1;
          })
          .slice(0, 6)
      : [];

  const addTag = (raw: string) => {
    const value = raw.trim();
    if (!value || values.includes(value)) return;
    onChange([...values, value]);
    setDraft("");
  };

  const removeTag = (value: string) => {
    onChange(values.filter((v) => v !== value));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag(draft);
    } else if (e.key === "Backspace" && draft === "" && values.length > 0) {
      removeTag(values[values.length - 1]);
    }
  };

  return (
    <div className="space-y-2">
      <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </label>

      <div className="relative">
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-input bg-card px-3 py-2.5 focus-within:ring-2 focus-within:ring-ring">
          {values.map((value) => (
            <span
              key={value}
              className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary"
            >
              {value}
              <button
                type="button"
                onClick={() => removeTag(value)}
                className="rounded-full hover:bg-primary/20"
                aria-label={`Retirer ${value}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={() => addTag(draft)}
            placeholder={values.length === 0 ? placeholder : ""}
            className="min-w-[120px] flex-1 border-none bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
        </div>

        {filteredSuggestions.length > 0 && (
          <div className="absolute z-10 mt-1 w-full overflow-hidden rounded-xl border border-border bg-card shadow-lift">
            {filteredSuggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  addTag(suggestion);
                }}
                className={cn(
                  "block w-full px-3 py-2 text-left text-sm text-foreground hover:bg-muted"
                )}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
      </div>

      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
