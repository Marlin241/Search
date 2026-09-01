"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, Copy, X } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { admin } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { AdminAccessRequest } from "@/lib/types";

const RANK: Record<AdminAccessRequest["status"], number> = {
  pending: 0,
  approved: 1,
  dismissed: 2,
};

export function AccessRequestsTab() {
  const { token } = useAuth();
  const [items, setItems] = useState<AdminAccessRequest[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

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
      if (RANK[a.status] !== RANK[b.status]) return RANK[a.status] - RANK[b.status];
      return b.created_at.localeCompare(a.created_at);
    });
  }, [items]);

  const act = async (
    id: number,
    fn: (token: string, id: number) => Promise<AdminAccessRequest>,
    successMsg: (updated: AdminAccessRequest) => string
  ) => {
    if (!token) return;
    setBusyId(id);
    try {
      const updated = await fn(token, id);
      setItems((prev) => prev?.map((r) => (r.id === id ? updated : r)) ?? prev);
      toast.success(successMsg(updated));
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Échec de l'action.");
    } finally {
      setBusyId(null);
    }
  };

  const approve = (id: number) =>
    act(
      id,
      admin.approveAccessRequest,
      (u) => `Code envoyé à ${u.email}${u.invite_code ? ` (${u.invite_code})` : ""}`
    );

  const dismiss = (id: number) =>
    act(id, admin.dismissAccessRequest, (u) => `Demande de ${u.email} écartée`);

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
        <Card key={r.id} className={cn(r.status !== "pending" && "opacity-70")}>
          <CardContent className="space-y-2 p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 text-xs text-muted-foreground">
                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard?.writeText(r.email);
                    toast.success("Email copié");
                  }}
                  className="inline-flex items-center gap-1 font-medium text-foreground hover:underline"
                  title="Copier l'email"
                >
                  {r.email}
                  <Copy className="h-3 w-3" />
                </button>
                {" · "}
                {formatRelativeTime(r.created_at)}
              </div>

              {r.status === "pending" ? (
                <div className="flex shrink-0 gap-2">
                  <Button
                    size="sm"
                    variant="primary"
                    isLoading={busyId === r.id}
                    onClick={() => approve(r.id)}
                  >
                    Approuver
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busyId === r.id}
                    onClick={() => dismiss(r.id)}
                  >
                    Écarter
                  </Button>
                </div>
              ) : r.status === "approved" ? (
                <span className="flex shrink-0 items-center gap-1 text-xs text-success">
                  <Check className="h-3.5 w-3.5" /> Approuvé
                </span>
              ) : (
                <span className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
                  <X className="h-3.5 w-3.5" /> Écartée
                </span>
              )}
            </div>

            {r.note && (
              <p className="whitespace-pre-wrap text-sm text-foreground">
                {r.note}
              </p>
            )}

            {r.status === "approved" && r.invite_code && (
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard?.writeText(r.invite_code ?? "");
                  toast.success("Code copié");
                }}
                className="inline-flex items-center gap-1.5 rounded-md bg-muted px-2 py-1 font-mono text-xs text-foreground hover:bg-muted/70"
                title="Copier le code"
              >
                Code envoyé : {r.invite_code}
                <Copy className="h-3 w-3" />
              </button>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
