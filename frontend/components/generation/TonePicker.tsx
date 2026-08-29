"use client";

import { cn } from "@/lib/utils";
import type { LetterTone } from "@/lib/types";

const TONES: { value: LetterTone; label: string }[] = [
  { value: "sobre", label: "Sobre" },
  { value: "chaleureux", label: "Chaleureux" },
  { value: "direct", label: "Direct" },
  { value: "formel", label: "Formel" },
];

export function TonePicker({
  value,
  onChange,
}: {
  value: LetterTone;
  onChange: (value: LetterTone) => void;
}) {
  return (
    <div className="inline-flex rounded-lg border border-border/80 bg-secondary p-1">
      {TONES.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={cn(
            "px-3 py-1.5 text-xs font-semibold rounded-md transition-colors",
            value === option.value
              ? "bg-card text-foreground shadow-soft"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
