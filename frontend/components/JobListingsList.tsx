"use client";

import { useState } from "react";
import { SearchX } from "lucide-react";
import { Card } from "./ui/Card";
import { Button } from "./ui/Button";
import type { JobListing } from "@/lib/types";

interface JobListingsListProps {
  listings: JobListing[];
  unavailableSources: string[];
  onCreateApplications: (selected: JobListing[]) => void;
  isCreating: boolean;
}

export function JobListingsList({ listings, unavailableSources, onCreateApplications, isCreating }: JobListingsListProps) {
  const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());

  function toggle(url: string) {
    setSelectedUrls((prev) => {
      const next = new Set(prev);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });
  }

  function handleCreate() {
    onCreateApplications(listings.filter((listing) => selectedUrls.has(listing.url)));
  }

  return (
    <div>
      {unavailableSources.length > 0 && (
        <p className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
          Sources indisponibles pour cette recherche : {unavailableSources.join(", ")}
        </p>
      )}

      {listings.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-10 text-center">
          <SearchX className="h-6 w-6 text-slate-400 dark:text-slate-500" aria-hidden="true" />
          <p className="text-sm text-slate-600 dark:text-slate-400">Aucune offre trouvée pour ces critères.</p>
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {listings.map((listing) => (
            <li key={listing.url}>
              <Card className="flex items-start gap-3 p-4">
                <input
                  type="checkbox"
                  aria-label={listing.title}
                  checked={selectedUrls.has(listing.url)}
                  onChange={() => toggle(listing.url)}
                  className="mt-1 h-4 w-4 rounded border-slate-300 text-amber-600 focus:ring-amber-500 dark:border-ink-800"
                />
                <div>
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">{listing.title}</p>
                  <p className="text-sm text-slate-600 dark:text-slate-400">
                    {listing.company}
                    {listing.location ? ` — ${listing.location}` : ""}
                  </p>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-500">{listing.snippet}</p>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      <Button onClick={handleCreate} disabled={selectedUrls.size === 0} isLoading={isCreating} className="mt-4">
        {isCreating ? "Lancement en cours..." : `Lancer le diagnostic pour la sélection (${selectedUrls.size})`}
      </Button>
    </div>
  );
}
