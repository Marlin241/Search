"use client";

import { History } from "lucide-react";
import type { ChangelogEntry } from "@/lib/types";

export function ChangelogList({ entries }: { entries: ChangelogEntry[] }) {
  if (entries.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
        <History className="w-3.5 h-3.5" /> Changements apportés
      </p>
      <ul className="space-y-2">
        {entries.map((entry, i) => (
          <li key={i} className="text-xs border-l-2 border-border pl-3">
            <span className="font-semibold text-foreground">{entry.section}</span>
            <p className="text-foreground">{entry.change}</p>
            <p className="text-muted-foreground italic">{entry.reason}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
