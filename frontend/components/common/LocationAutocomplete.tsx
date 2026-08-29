"use client";

import { useMemo, useState } from "react";
import { MapPin } from "lucide-react";
import { cn } from "@/lib/utils";
import { useCityList } from "@/lib/useCityList";

// Accent-insensitive, mirrors TagInput / the backend keyword_matching
// convention (French users type "thies" and expect "Thiès").
function normalize(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

export interface LocationAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  placeholder?: string;
  id?: string;
}

export function LocationAutocomplete({
  value,
  onChange,
  label = "Localisation",
  placeholder = "ex : Dakar, Abidjan, Paris...",
  id = "location-autocomplete",
}: LocationAutocompleteProps) {
  const cities = useCityList();
  const [open, setOpen] = useState(false);

  const suggestions = useMemo(() => {
    const q = normalize(value.trim());
    if (!q) return [];
    const matches = cities
      .filter((c) => normalize(c).includes(q))
      .sort((a, b) => {
        const aStarts = normalize(a).startsWith(q) ? 0 : 1;
        const bStarts = normalize(b).startsWith(q) ? 0 : 1;
        return aStarts - bStarts;
      })
      .slice(0, 8);
    // Hide the dropdown once the field exactly equals its only match.
    return matches.length === 1 && normalize(matches[0]) === q ? [] : matches;
  }, [cities, value]);

  return (
    <div className="w-full space-y-1.5">
      {label && (
        <label
          htmlFor={id}
          className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground"
        >
          {label}
        </label>
      )}
      <div className="relative">
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground">
          <MapPin className="h-4 w-4" />
        </div>
        <input
          id={id}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          placeholder={placeholder}
          autoComplete="off"
          className={cn(
            "flex h-10 w-full rounded-lg border border-input bg-card px-3 py-2 pl-9 text-sm transition-colors",
            "placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:border-primary"
          )}
        />
        {open && suggestions.length > 0 && (
          <div className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-border bg-card shadow-lg">
            {suggestions.map((city) => (
              <button
                key={city}
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  onChange(city);
                  setOpen(false);
                }}
                className="block w-full px-3 py-2 text-left text-sm text-foreground hover:bg-muted"
              >
                {city}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
