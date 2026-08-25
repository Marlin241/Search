"use client";

import { CheckCircle2, CircleDot, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { KeywordOmission } from "@/lib/types";

export function KeywordTransparency({
  added,
  alreadyPresent,
  omitted,
}: {
  added: string[];
  alreadyPresent: string[];
  omitted: KeywordOmission[];
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-success flex items-center gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5" /> Ajoutés ({added.length})
        </p>
        <div className="flex flex-wrap gap-1.5">
          {added.map((kw) => (
            <Badge key={kw} variant="success">
              {kw}
            </Badge>
          ))}
          {added.length === 0 && (
            <p className="text-xs text-muted-foreground">Aucun</p>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
          <CircleDot className="w-3.5 h-3.5" /> Déjà présents ({alreadyPresent.length})
        </p>
        <div className="flex flex-wrap gap-1.5">
          {alreadyPresent.map((kw) => (
            <Badge key={kw} variant="default">
              {kw}
            </Badge>
          ))}
          {alreadyPresent.length === 0 && (
            <p className="text-xs text-muted-foreground">Aucun</p>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-warning-dark flex items-center gap-1.5">
          <XCircle className="w-3.5 h-3.5" /> Omis volontairement ({omitted.length})
        </p>
        <div className="space-y-1.5">
          {omitted.map((item) => (
            <div key={item.keyword} className="text-xs">
              <span className="font-semibold text-foreground">{item.keyword}</span>
              <p className="text-muted-foreground">{item.reason}</p>
            </div>
          ))}
          {omitted.length === 0 && (
            <p className="text-xs text-muted-foreground">Aucun</p>
          )}
        </div>
      </div>
    </div>
  );
}
