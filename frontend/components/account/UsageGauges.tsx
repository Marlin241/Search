"use client";

import { useEffect, useState } from "react";
import { Gauge } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { getUsage } from "@/lib/api";
import type { UsageItem } from "@/lib/types";

export function UsageGauges() {
  const { token } = useAuth();
  const [items, setItems] = useState<UsageItem[] | null>(null);

  useEffect(() => {
    if (!token) return;
    getUsage(token)
      .then(setItems)
      .catch(() => setItems(null));
  }, [token]);

  if (!items || items.length === 0) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Gauge className="w-4 h-4 text-muted-foreground" />
        <h3 className="text-base font-bold font-display text-foreground">
          Ton utilisation ce mois-ci (beta)
        </h3>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {items.map((item) => {
          const pct = Math.min(
            100,
            item.limit > 0 ? (item.used / item.limit) * 100 : 0
          );
          return (
            <div key={item.feature} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-foreground">{item.label}</span>
                <span className="text-muted-foreground">
                  {item.used} / {item.limit}
                </span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary-500 rounded-full transition-all"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <p className="text-[11px] text-muted-foreground">
                Réinitialisation le {item.reset_date}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
