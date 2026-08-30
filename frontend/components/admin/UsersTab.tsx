"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { admin } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { cn, formatDate, formatRelativeTime } from "@/lib/utils";
import type { AdminUser } from "@/lib/types";

function UserDetail({
  user,
  onChange,
}: {
  user: AdminUser;
  onChange: (u: AdminUser) => void;
}) {
  const { token, user: me } = useAuth();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const saveQuota = async (feature: string) => {
    if (!token) return;
    const raw = drafts[feature] ?? "";
    const limit = raw.trim() === "" ? null : Number(raw);
    if (limit !== null && (!Number.isFinite(limit) || limit < 0)) {
      setError("Valeur invalide.");
      return;
    }
    setBusy(feature);
    setError(null);
    try {
      onChange(await admin.patchUserQuota(token, user.id, feature, limit));
      setDrafts((d) => {
        const next = { ...d };
        delete next[feature];
        return next;
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Échec.");
    } finally {
      setBusy(null);
    }
  };

  const toggleActive = async () => {
    if (!token) return;
    setBusy("active");
    setError(null);
    try {
      onChange(await admin.patchUserActive(token, user.id, !user.is_active));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Échec.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-4 border-t border-border/60 bg-muted/20 px-4 py-4">
      {error && <p className="text-xs text-destructive">{error}</p>}

      <div className="grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
        <p className="text-muted-foreground">
          Consentement :{" "}
          <span className="text-foreground">
            {user.consent_version ?? "—"}
            {user.consent_accepted_at
              ? ` (${formatDate(user.consent_accepted_at)})`
              : ""}
          </span>
        </p>
        <p className="text-muted-foreground">
          Dernière activité :{" "}
          <span className="text-foreground">
            {user.last_activity_at
              ? formatRelativeTime(user.last_activity_at)
              : "aucune"}
          </span>
        </p>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Quotas mensuels
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          {user.usage.map((item) => {
            const overridden =
              user.quota_overrides != null &&
              item.feature in user.quota_overrides;
            const pct =
              item.limit > 0
                ? Math.min(100, (item.used / item.limit) * 100)
                : 0;
            return (
              <div
                key={item.feature}
                className="space-y-1 rounded-lg border border-border/60 bg-card p-2.5"
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-foreground">
                    {item.label}
                  </span>
                  <span className="text-muted-foreground">
                    {item.used} / {item.limit}
                    {overridden && (
                      <span className="ml-1 text-primary">(ajusté)</span>
                    )}
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary-500"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="flex items-center gap-1.5 pt-1">
                  <input
                    type="number"
                    min={0}
                    placeholder="défaut"
                    value={drafts[item.feature] ?? ""}
                    onChange={(e) =>
                      setDrafts((d) => ({
                        ...d,
                        [item.feature]: e.target.value,
                      }))
                    }
                    className="h-7 w-24 rounded-md border border-input bg-card px-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7"
                    isLoading={busy === item.feature}
                    onClick={() => saveQuota(item.feature)}
                  >
                    {(drafts[item.feature] ?? "").trim() === "" && overridden
                      ? "Réinitialiser"
                      : "Appliquer"}
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button
          size="sm"
          variant={user.is_active ? "danger" : "primary"}
          isLoading={busy === "active"}
          disabled={user.id === me?.id}
          onClick={toggleActive}
        >
          {user.is_active ? "Désactiver le compte" : "Réactiver le compte"}
        </Button>
        {user.id === me?.id && (
          <span className="text-xs text-muted-foreground">
            (impossible sur ton propre compte)
          </span>
        )}
      </div>
    </div>
  );
}

export function UsersTab() {
  const { token } = useAuth();
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    admin
      .getUsers(token)
      .then(setUsers)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Erreur de chargement.")
      );
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const patchOne = (u: AdminUser) =>
    setUsers((prev) => prev?.map((x) => (x.id === u.id ? u : x)) ?? prev);

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!users) return <p className="text-sm text-muted-foreground">Chargement…</p>;
  if (users.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">Aucun inscrit pour l'instant.</p>
    );
  }

  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/60 text-left text-xs uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-3 font-semibold">Email</th>
                <th className="px-4 py-3 font-semibold">Inscrit le</th>
                <th className="px-4 py-3 font-semibold">Invitation</th>
                <th className="px-4 py-3 font-semibold">Dernier usage</th>
                <th className="px-4 py-3 font-semibold">Actif</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <Fragment key={u.id}>
                  <tr
                    className="cursor-pointer border-b border-border/40 hover:bg-muted/30"
                    onClick={() =>
                      setExpanded((cur) => (cur === u.id ? null : u.id))
                    }
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        {expanded === u.id ? (
                          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                        )}
                        <span className="font-medium text-foreground">
                          {u.email}
                        </span>
                        {u.is_admin && (
                          <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-bold text-primary">
                            admin
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatDate(u.created_at)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {u.invite_note ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {u.last_activity_at
                        ? formatRelativeTime(u.last_activity_at)
                        : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-block h-2 w-2 rounded-full",
                          u.is_active ? "bg-success" : "bg-destructive"
                        )}
                      />
                    </td>
                  </tr>
                  {expanded === u.id && (
                    <tr>
                      <td colSpan={5} className="p-0">
                        <UserDetail user={u} onChange={patchOne} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
