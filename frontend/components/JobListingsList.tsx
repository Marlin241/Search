"use client";

import { useState } from "react";
import { SearchX, MapPin, Check, Wifi } from "lucide-react";
import { Button } from "./ui/Button";
import { Badge } from "./ui/Badge";
import { sourceLabel, isLikelyRemote } from "@/lib/jobListingPresentation";
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
        <div className="flex flex-col items-center gap-3 rounded-3xl border border-dashed border-border bg-surface-2/50 px-6 py-14 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-accent-soft text-accent-ink">
            <SearchX className="h-7 w-7" aria-hidden="true" />
          </span>
          <p className="font-display text-base font-bold text-ink">Aucune offre ne correspond à ces critères</p>
          <p className="max-w-sm text-sm text-ink-soft">
            Essaie un mot-clé plus court, retire le filtre télétravail, ou élargis la localisation.
          </p>
        </div>
      ) : (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {listings.map((listing) => {
            const isSelected = selectedUrls.has(listing.url);
            const remote = isLikelyRemote(listing);
            return (
              <li key={listing.url}>
                <label
                  className={`lift group relative flex h-full cursor-pointer flex-col overflow-hidden rounded-3xl border bg-surface p-5 shadow-soft transition-all ${
                    isSelected ? "border-accent/50" : "border-border hover:border-border-strong"
                  }`}
                >
                  {isSelected && <span className="absolute inset-y-0 left-0 w-1.5 bg-accent-strong" aria-hidden="true" />}
                  <input
                    type="checkbox"
                    aria-label={listing.title}
                    checked={isSelected}
                    onChange={() => toggle(listing.url)}
                    className="sr-only"
                  />
                  <div className={`flex items-start justify-between gap-2.5 ${isSelected ? "pl-1.5" : ""}`}>
                    <span className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-2xl bg-accent-soft font-display text-lg font-extrabold text-accent-ink">
                      {initials(listing.company)}
                    </span>
                    <span
                      className={`inline-flex flex-shrink-0 items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-bold transition-colors ${
                        isSelected
                          ? "bg-accent-strong text-ink-on-accent"
                          : "bg-surface-2 text-ink-soft group-hover:bg-accent-soft group-hover:text-accent-ink"
                      }`}
                    >
                      {isSelected && <Check className="h-3.5 w-3.5" strokeWidth={3} aria-hidden="true" />}
                      {isSelected ? "Sélectionnée" : "Sélectionner"}
                    </span>
                  </div>
                  <p className={`mt-4 font-display text-base font-bold leading-tight text-ink ${isSelected ? "pl-1.5" : ""}`}>
                    {listing.title}
                  </p>
                  <p className={`mt-1 text-[13.5px] font-semibold text-ink-soft ${isSelected ? "pl-1.5" : ""}`}>
                    {listing.company}
                  </p>
                  <div className={`mt-2.5 flex flex-wrap items-center gap-1.5 ${isSelected ? "pl-1.5" : ""}`}>
                    {listing.location && (
                      <Badge variant="neutral" className="gap-1 font-semibold">
                        <MapPin className="h-3 w-3 flex-shrink-0" aria-hidden="true" />
                        {listing.location}
                      </Badge>
                    )}
                    <Badge variant="neutral">{sourceLabel(listing.source)}</Badge>
                    {remote && (
                      <Badge variant="accent2" className="gap-1">
                        <Wifi className="h-3 w-3 flex-shrink-0" aria-hidden="true" />
                        Télétravail
                      </Badge>
                    )}
                  </div>
                  <p className={`mt-3 flex-1 text-xs leading-relaxed text-ink-faint ${isSelected ? "pl-1.5" : ""}`}>
                    {listing.snippet}
                  </p>
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
