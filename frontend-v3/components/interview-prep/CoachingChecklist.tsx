import { CheckSquare } from "lucide-react";
import type { CoachingChecklistContent } from "@/lib/types";

const SECTIONS: { key: keyof CoachingChecklistContent; label: string }[] = [
  { key: "before", label: "Avant l'entretien" },
  { key: "during", label: "Pendant l'entretien" },
  { key: "after", label: "Après l'entretien" },
];

export function CoachingChecklist({ checklist }: { checklist: CoachingChecklistContent }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {SECTIONS.map(({ key, label }) => (
        <div key={key} className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {label}
          </p>
          <ul className="space-y-1.5">
            {checklist[key].map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-foreground">
                <CheckSquare className="w-3.5 h-3.5 mt-0.5 shrink-0 text-primary" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
