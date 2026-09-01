"use client";

import { useCallback, useEffect, useState } from "react";
import { Copy, Check } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { admin } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { cn, formatDate } from "@/lib/utils";
import type { AdminInvite } from "@/lib/types";

export function InvitesTab() {
  const { token } = useAuth();
  const [invites, setInvites] = useState<AdminInvite[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [count, setCount] = useState("5");
  const [note, setNote] = useState("");
  const [creating, setCreating] = useState(false);
  const [freshCodes, setFreshCodes] = useState<string[]>([]);
  const [copied, setCopied] = useState(false);

  const load = useCallback(() => {
    if (!token) return;
    admin
      .getInvites(token)
      .then(setInvites)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Erreur de chargement.")
      );
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async () => {
    if (!token) return;
    const n = Number(count);
    if (!Number.isInteger(n) || n < 1 || n > 50) {
      setError("Entre 1 et 50 codes à la fois.");
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const { codes } = await admin.createInvites(token, n, note.trim() || null);
      setFreshCodes(codes);
      setNote("");
      load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Échec de la génération.");
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (code: string) => {
    if (!token) return;
    try {
      await admin.revokeInvite(token, code);
      load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Échec de la révocation.");
    }
  };

  const copyFresh = async () => {
    try {
      await navigator.clipboard.writeText(freshCodes.join("\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-4 p-5">
          <h3 className="font-display text-sm font-bold text-foreground">
            Générer des codes d'invitation
          </h3>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-24">
              <Input
                label="Nombre"
                type="number"
                min={1}
                max={50}
                value={count}
                onChange={(e) => setCount(e.target.value)}
              />
            </div>
            <div className="min-w-[12rem] flex-1">
              <Input
                label="Note (ex. « vague 1 »)"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </div>
            <Button isLoading={creating} onClick={handleCreate}>
              Générer
            </Button>
          </div>

          {freshCodes.length > 0 && (
            <div className="space-y-2 rounded-xl border border-primary/30 bg-primary/5 p-3">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-foreground">
                  {freshCodes.length} code(s) généré(s) — à copier maintenant
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  icon={
                    copied ? (
                      <Check className="h-3.5 w-3.5" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )
                  }
                  onClick={copyFresh}
                >
                  {copied ? "Copié" : "Copier"}
                </Button>
              </div>
              <pre className="overflow-x-auto whitespace-pre-wrap break-all font-mono text-xs text-foreground">
                {freshCodes.join("\n")}
              </pre>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {!invites ? (
            <p className="p-5 text-sm text-muted-foreground">Chargement…</p>
          ) : invites.length === 0 ? (
            <p className="p-5 text-sm text-muted-foreground">
              Aucun code pour l'instant.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/60 text-left text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="px-4 py-3 font-semibold">Code</th>
                    <th className="px-4 py-3 font-semibold">Note</th>
                    <th className="px-4 py-3 font-semibold">Créé le</th>
                    <th className="px-4 py-3 font-semibold">Statut</th>
                    <th className="px-4 py-3 font-semibold" />
                  </tr>
                </thead>
                <tbody>
                  {invites.map((inv) => (
                    <tr
                      key={inv.code}
                      className="border-b border-border/40 last:border-0"
                    >
                      <td className="px-4 py-3 font-mono text-xs text-foreground">
                        {inv.code}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {inv.note ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {formatDate(inv.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "text-xs",
                            inv.used_by_email
                              ? "text-muted-foreground"
                              : "font-semibold text-success"
                          )}
                        >
                          {inv.used_by_email
                            ? `Utilisé par ${inv.used_by_email}`
                            : "Libre"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {!inv.used_by_email && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-destructive hover:bg-destructive/10"
                            onClick={() => handleRevoke(inv.code)}
                          >
                            Révoquer
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
