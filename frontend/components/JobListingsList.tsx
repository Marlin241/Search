"use client";

import { useState } from "react";
import { SearchX, MapPin, Check } from "lucide-react";
import { Button } from "./ui/Button";
import { Badge } from "./ui/Badge";
import type { JobListing } from "@/lib/types";

interface JobListingsListProps {
  listings: JobListing[];
  unavailableSources: string[];
  onCreateApplications: (selected: JobListing[]) => void;
  isCreating: boolean;
}

function initials(company: string): string {
  const words = company.trim().split(/\s+/).filter(Boolean);
  return (words[0]?.[0] ?? "") + (words[1]?.[0] ?? "");
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
        <p className="mb-4 rounded-2xl bg-pending-soft px-4 py-2.5 text-sm font-medium text-pending-ink">
          Sources indisponibles pour cette recherche : {unavailableSources.join(", ")}
        </p>
      )}

      {listings.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-10 text-center">
          <SearchX className="h-6 w-6 text-ink-faint" aria-hidden="true" />
          <p className="text-sm text-ink-soft">Aucune offre trouvée pour ces critères.</p>
        </div>
      ) : (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {listings.map((listing) => {
            const isSelected = selectedUrls.has(listing.url);
            return (
              <li key={listing.url}>
                <label
                  className={`lift flex h-full cursor-pointer flex-col rounded-3xl border-[1.5px] p-5 transition-colors ${
                    isSelected
                      ? "border-accent bg-accent-soft"
                      : "border-border bg-surface hover:border-border-strong hover:bg-surface-2"
                  }`}
                >
                  <input
                    type="checkbox"
                    aria-label={listing.title}
                    checked={isSelected}
                    onChange={() => toggle(listing.url)}
                    className="sr-only"
                  />
                  <div className="flex items-start justify-between gap-2.5">
                    <span className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-2xl bg-accent-soft font-display text-base font-extrabold text-accent-ink">
                      {initials(listing.company)}
                    </span>
                    <Badge variant="neutral">{listing.source}</Badge>
                  </div>
                  <p className="mt-3.5 font-display text-base font-bold leading-tight text-ink">{listing.title}</p>
                  <p className="mt-1 text-[13.5px] font-semibold text-ink-soft">{listing.company}</p>
                  {listing.location && (
                    <p className="mt-1.5 flex items-center gap-1.5 text-xs text-ink-faint">
                      <MapPin className="h-3 w-3 flex-shrink-0" aria-hidden="true" />
                      {listing.location}
                    </p>
                  )}
                  <p className="mt-3 flex-1 text-xs leading-relaxed text-ink-faint">{listing.snippet}</p>
                  <span
                    className={`mt-3.5 inline-flex w-fit items-center gap-1.5 rounded-full px-3.5 py-2 text-xs font-bold ${
                      isSelected ? "bg-accent-strong text-ink-on-accent" : "bg-surface-2 text-ink-soft"
                    }`}
                  >
                    {isSelected && <Check className="h-3 w-3" strokeWidth={3} aria-hidden="true" />}
                    {isSelected ? "Sélectionnée" : "Sélectionner"}
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      )}

      <Button onClick={handleCreate} disabled={selectedUrls.size === 0} isLoading={isCreating} className="mt-5">
        {isCreating ? "Lancement en cours..." : `Lancer le diagnostic pour la sélection (${selectedUrls.size})`}
      </Button>
    </div>
  );
}
