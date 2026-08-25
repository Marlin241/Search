"use client";

import { Globe } from "lucide-react";
import { cn } from "@/lib/utils";

export function WebSearchToggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={cn(
        "flex w-full items-start gap-3 rounded-xl border p-4 text-left transition-all",
        checked ? "border-primary bg-primary/5 ring-2 ring-primary/30" : "border-border hover:border-primary/40"
      )}
    >
      <div
        className={cn(
          "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
          checked ? "bg-primary text-white" : "bg-secondary text-muted-foreground"
        )}
      >
        <Globe className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-bold text-foreground">Rechercher les actualités de l&apos;entreprise</p>
          <span
            className={cn(
              "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors",
              checked ? "bg-primary" : "bg-border"
            )}
          >
            <span
              className={cn(
                "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
                checked ? "translate-x-4" : "translate-x-0.5"
              )}
            />
          </span>
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Enrichit le dossier avec des faits vérifiés et l&apos;actualité récente de l&apos;entreprise.
          {checked ? " Ajoute environ 5 minutes de génération." : " Sans cette option, les faits sont marqués comme non vérifiés."}
        </p>
      </div>
    </button>
  );
}
