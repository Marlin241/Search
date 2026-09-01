"use client";

import { useCallback, useEffect, useState } from "react";
import { Users, Activity, Sparkles, Coins } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { admin } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import type { AdminOverview } from "@/lib/types";

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Users;
  label: string;
  value: string | number;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="font-display text-2xl font-bold text-foreground">
            {value}
          </p>
          <p className="text-xs text-muted-foreground">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}

export function OverviewTab() {
  const { token } = useAuth();
  const [data, setData] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState(false);

  const load = useCallback(() => {
    if (!token) return;
    admin
      .getOverview(token)
      .then(setData)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Erreur de chargement.")
      );
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const handleToggle = async () => {
    if (!token || !data) return;
    setToggling(true);
    try {
      const { enabled } = await admin.toggleLlm(token, !data.llm_features_enabled);
      setData({ ...data, llm_features_enabled: enabled });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Échec de la bascule.");
    } finally {
      setToggling(false);
    }
  };

  if (error) {
    return <p className="text-sm text-destructive">{error}</p>;
  }
  if (!data) {
    return <p className="text-sm text-muted-foreground">Chargement…</p>;
  }

  const totalCalls = Object.values(data.llm_calls_this_month).reduce(
    (a, b) => a + b,
    0
  );
  const totalTokens =
    data.tokens_this_month.input + data.tokens_this_month.output;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Users} label="Inscrits" value={data.users_total} />
        <StatCard
          icon={Activity}
          label="Actifs (7 j)"
          value={data.users_active_7d}
        />
        <StatCard
          icon={Sparkles}
          label="Appels LLM ce mois"
          value={totalCalls}
        />
        <StatCard
          icon={Coins}
          label="Tokens ce mois"
          value={totalTokens.toLocaleString("fr-FR")}
        />
      </div>

      <Card>
        <CardContent className="space-y-3 p-5">
          <h3 className="font-display text-sm font-bold text-foreground">
            Appels par fonctionnalité (ce mois)
          </h3>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(data.llm_calls_this_month).map(([feature, count]) => (
              <div
                key={feature}
                className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2 text-xs"
              >
                <span className="text-muted-foreground">{feature}</span>
                <span className="font-semibold text-foreground">{count}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">
              Fonctionnalités LLM :{" "}
              <span
                className={
                  data.llm_features_enabled
                    ? "text-success font-bold"
                    : "text-destructive font-bold"
                }
              >
                {data.llm_features_enabled ? "ON" : "OFF"}
              </span>
            </p>
            <p className="text-xs text-muted-foreground">
              Interrupteur global. OFF met en pause toutes les générations IA.
            </p>
          </div>
          <Button
            variant={data.llm_features_enabled ? "danger" : "primary"}
            size="sm"
            isLoading={toggling}
            onClick={handleToggle}
          >
            {data.llm_features_enabled ? "Mettre en pause" : "Réactiver"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
