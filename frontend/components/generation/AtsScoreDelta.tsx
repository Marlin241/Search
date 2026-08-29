"use client";

import { ArrowRight } from "lucide-react";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { Badge } from "@/components/ui/Badge";

export function AtsScoreDelta({ before, after }: { before: number; after: number }) {
  const delta = after - before;

  return (
    <div className="flex items-center justify-center gap-4">
      <ScoreRing score={before} size="sm" label="Avant" />
      <ArrowRight className="w-5 h-5 text-muted-foreground shrink-0" />
      <ScoreRing score={after} size="md" label="Après" />
      {delta !== 0 && (
        <Badge variant={delta > 0 ? "success" : "destructive"} size="md">
          {delta > 0 ? "+" : ""}
          {delta} pts
        </Badge>
      )}
    </div>
  );
}
