"use client";

import { useEffect, useState } from "react";

// Curated city list served from public/locations.json (West/Central Africa +
// France). Fetched once, cached at module scope, shared by every consumer.
// On any failure the list stays empty and the inputs degrade to free text.
let cache: string[] | null = null;
let inFlight: Promise<string[]> | null = null;

async function load(): Promise<string[]> {
  if (cache) return cache;
  if (!inFlight) {
    inFlight = fetch("/locations.json")
      .then((r) => (r.ok ? r.json() : []))
      .then((data: unknown) => {
        cache = Array.isArray(data) ? (data as string[]) : [];
        return cache;
      })
      .catch(() => {
        cache = [];
        return cache;
      });
  }
  return inFlight;
}

export function useCityList(): string[] {
  const [cities, setCities] = useState<string[]>(cache ?? []);
  useEffect(() => {
    let alive = true;
    load().then((list) => {
      if (alive) setCities(list);
    });
    return () => {
      alive = false;
    };
  }, []);
  return cities;
}
