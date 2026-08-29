"use client";

import { TemplatePicker } from "@/components/generation/TemplatePicker";
import type { CvStyleOptions, CvTemplate } from "@/lib/types";

const SPACING_OPTIONS: { value: NonNullable<CvStyleOptions["spacing"]>; label: string }[] = [
  { value: "compact", label: "Compact" },
  { value: "normal", label: "Normal" },
  { value: "relaxed", label: "Aéré" },
];

export function StyleControls({
  template,
  onTemplateChange,
  style,
  onStyleChange,
}: {
  template: CvTemplate;
  onTemplateChange: (template: CvTemplate) => void;
  style: CvStyleOptions;
  onStyleChange: (style: CvStyleOptions) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Modèle
        </label>
        <TemplatePicker value={template} onChange={onTemplateChange} />
      </div>

      <div className="space-y-1.5">
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Couleur d&apos;accent
        </label>
        <input
          type="color"
          value={style.accent_color ?? "#2563eb"}
          onChange={(e) => onStyleChange({ ...style, accent_color: e.target.value })}
          className="h-9 w-16 rounded-lg border border-input cursor-pointer bg-card"
        />
      </div>

      <div className="space-y-1.5">
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Marges ({style.margins ?? 15}mm)
        </label>
        <input
          type="range"
          min={10}
          max={25}
          value={style.margins ?? 15}
          onChange={(e) => onStyleChange({ ...style, margins: Number(e.target.value) })}
          className="w-full"
        />
      </div>

      <div className="space-y-1.5">
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Espacement
        </label>
        <div className="inline-flex rounded-lg border border-border/80 bg-secondary p-1">
          {SPACING_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => onStyleChange({ ...style, spacing: option.value })}
              className={
                "px-3 py-1.5 text-xs font-semibold rounded-md transition-colors " +
                ((style.spacing ?? "normal") === option.value
                  ? "bg-card text-foreground shadow-soft"
                  : "text-muted-foreground hover:text-foreground")
              }
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
