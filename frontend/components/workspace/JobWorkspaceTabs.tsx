"use client";

import { Briefcase, FileText, Mail, MessagesSquare } from "lucide-react";
import { cn } from "@/lib/utils";

export type WorkspaceTab = "offre" | "cv" | "lettre" | "entretien";

const TABS: { id: WorkspaceTab; label: string; icon: typeof Briefcase }[] = [
  { id: "offre", label: "Offre", icon: Briefcase },
  { id: "cv", label: "CV", icon: FileText },
  { id: "lettre", label: "Lettre", icon: Mail },
  { id: "entretien", label: "Entretien", icon: MessagesSquare },
];

export function JobWorkspaceTabs({
  active,
  onChange,
}: {
  active: WorkspaceTab;
  onChange: (tab: WorkspaceTab) => void;
}) {
  return (
    <div className="flex items-center gap-1 border-b border-border overflow-x-auto">
      {TABS.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          className={cn(
            "flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-2 -mb-px transition-colors whitespace-nowrap",
            active === id
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          <Icon className="w-3.5 h-3.5" />
          {label}
        </button>
      ))}
    </div>
  );
}
