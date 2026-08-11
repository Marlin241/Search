"use client";

import { useState } from "react";
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
        <p className="mb-3 rounded-md border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-800">
          Sources indisponibles pour cette recherche : {unavailableSources.join(", ")}
        </p>
      )}

      {listings.length === 0 ? (
        <p className="text-sm text-slate-600">Aucune offre trouvée pour ces critères.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {listings.map((listing) => (
            <li key={listing.url} className="flex items-start gap-3 rounded-xl bg-white p-4 shadow-sm">
              <input
                type="checkbox"
                aria-label={listing.title}
                checked={selectedUrls.has(listing.url)}
                onChange={() => toggle(listing.url)}
                className="mt-1"
              />
              <div>
                <p className="text-sm font-semibold text-slate-900">{listing.title}</p>
                <p className="text-sm text-slate-600">
                  {listing.company}
                  {listing.location ? ` — ${listing.location}` : ""}
                </p>
                <p className="mt-1 text-xs text-slate-500">{listing.snippet}</p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={handleCreate}
        disabled={selectedUrls.size === 0 || isCreating}
        className="mt-4 rounded-md bg-blue-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        {isCreating ? "Lancement en cours..." : `Lancer le diagnostic pour la sélection (${selectedUrls.size})`}
      </button>
    </div>
  );
}
