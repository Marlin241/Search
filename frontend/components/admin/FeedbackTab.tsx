"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { admin } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { AdminFeedback } from "@/lib/types";

export function FeedbackTab() {
  const { token } = useAuth();
  const [items, setItems] = useState<AdminFeedback[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    admin
      .getFeedback(token)
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
      await admin.markFeedbackHandled(token, id);
      setItems(
        (prev) =>
          prev?.map((f) =>
            f.id === id ? { ...f, handled_at: new Date().toISOString() } : f
          ) ?? prev
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Échec.");
    }
  };

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!sorted) return <p className="text-sm text-muted-foreground">Chargement…</p>;
  if (sorted.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aucun retour pour l'instant.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {sorted.map((f) => (
        <Card key={f.id} className={cn(f.handled_at && "opacity-60")}>
          <CardContent className="space-y-2 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs text-muted-foreground">
                <span className="font-medium text-foreground">
                  {f.user_email ?? "anonyme"}
                </span>
                {" · "}
                {f.page || "—"}
                {" · "}
                {formatRelativeTime(f.created_at)}
              </div>
              {f.handled_at ? (
                <span className="flex items-center gap-1 text-xs text-success">
                  <Check className="h-3.5 w-3.5" /> Traité
                </span>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => markHandled(f.id)}
                >
                  Marquer traité
                </Button>
              )}
            </div>
            <p className="whitespace-pre-wrap text-sm text-foreground">
              {f.message}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
