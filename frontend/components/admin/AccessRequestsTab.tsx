"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, Copy } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { admin } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { AdminAccessRequest } from "@/lib/types";

export function AccessRequestsTab() {
  const { token } = useAuth();
  const [items, setItems] = useState<AdminAccessRequest[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    admin
      .getAccessRequests(token)
      .then(setItems)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Erreur de chargement.")
      );
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const sorted = useMemo(() => {
    if (!items) return null;
    return [...items].sort((a, b) => {
      if (!!a.handled_at !== !!b.handled_at) return a.handled_at ? 1 : -1;
      return b.created_at.localeCompare(a.created_at);
    });
  }, [items]);

  const markHandled = async (id: number) => {
    if (!token) return;
    try {
      await admin.markAccessRequestHandled(token, id);
      setItems(
        (prev) =>
          prev?.map((r) =>
            r.id === id ? { ...r, handled_at: new Date().toISOString() } : r
          ) ?? prev
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Échec.");
    }
  };

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!sorted)
    return <p className="text-sm text-muted-foreground">Chargement…</p>;
  if (sorted.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aucune demande d&apos;accès pour l&apos;instant.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {sorted.map((r) => (
        <Card key={r.id} className={cn(r.handled_at && "opacity-60")}>
          <CardContent className="space-y-2 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs text-muted-foreground">
                <button
                  type="button"
                  onClick={() => navigator.clipboard?.writeText(r.email)}
                  className="inline-flex items-center gap-1 font-medium text-foreground hover:underline"
                  title="Copier l'email"
                >
                  {r.email}
                  <Copy className="h-3 w-3" />
                </button>
                {" · "}
                {formatRelativeTime(r.created_at)}
              </div>
              {r.handled_at ? (
                <span className="flex items-center gap-1 text-xs text-success">
                  <Check className="h-3.5 w-3.5" /> Traité
                </span>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => markHandled(r.id)}
                >
                  Marquer traité
                </Button>
              )}
            </div>
            {r.note && (
              <p className="whitespace-pre-wrap text-sm text-foreground">
                {r.note}
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
