"use client";

import { cn } from "@/lib/utils";
import type { CvTemplate } from "@/lib/types";

const TEMPLATES: { value: CvTemplate; label: string }[] = [
  { value: "classic", label: "Classique" },
  { value: "modern", label: "Moderne" },
  { value: "minimal", label: "Minimal" },
];

export function TemplatePicker({
  value,
  onChange,
}: {
  value: CvTemplate;
  onChange: (value: CvTemplate) => void;
}) {
  return (
    <div className="inline-flex rounded-lg border border-border/80 bg-secondary p-1">
      {TEMPLATES.map((option) => (
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
