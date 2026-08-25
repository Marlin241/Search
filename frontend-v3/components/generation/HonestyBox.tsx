"use client";

import { Eye, ThumbsUp, TriangleAlert } from "lucide-react";
import type { HonestyAssessment } from "@/lib/types";

export function HonestyBox({ assessment }: { assessment: HonestyAssessment }) {
  return (
    <div className="rounded-xl border border-accent/30 bg-accent/5 p-4 space-y-3">
      <div className="flex items-center gap-2 text-accent-foreground font-semibold text-sm">
        <Eye className="w-4 h-4" />
        L&apos;œil honnête de l&apos;IA
      </div>
      <p className="text-sm text-foreground">{assessment.fit_summary}</p>

      {assessment.strengths.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-semibold uppercase tracking-wider text-success flex items-center gap-1.5">
            <ThumbsUp className="w-3.5 h-3.5" /> Points forts
          </p>
          <ul className="space-y-1">
            {assessment.strengths.map((item, i) => (
              <li key={i} className="text-xs text-muted-foreground pl-5 relative">
                <span className="absolute left-0">•</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {assessment.concerns.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-semibold uppercase tracking-wider text-warning-dark flex items-center gap-1.5">
            <TriangleAlert className="w-3.5 h-3.5" /> Points de vigilance
          </p>
          <ul className="space-y-1">
            {assessment.concerns.map((item, i) => (
              <li key={i} className="text-xs text-muted-foreground pl-5 relative">
                <span className="absolute left-0">•</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
