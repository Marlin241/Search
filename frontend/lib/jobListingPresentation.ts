import type { JobListing } from "./types";

const SOURCE_LABELS: Record<string, string> = {
  france_travail: "France Travail",
  adzuna: "Adzuna",
  la_bonne_alternance: "La Bonne Alternance",
  greenhouse: "Greenhouse",
  lever: "Lever",
};

export function sourceLabel(source: string): string {
  return (
    SOURCE_LABELS[source] ??
    source
      .split("_")
      .filter(Boolean)
      .map((word) => word[0].toUpperCase() + word.slice(1))
      .join(" ")
  );
}

// Mirrors the backend's REMOTE_INDICATORS heuristic (aggregator.py): none of
// the source APIs expose a clean boolean remote flag, so a listing is only
// flagged as remote-friendly here if its location or snippet says so.
const REMOTE_INDICATORS = ["remote", "télétravail", "distanciel"];

export function isLikelyRemote(listing: Pick<JobListing, "location" | "snippet">): boolean {
  const haystack = `${listing.location ?? ""} ${listing.snippet}`.toLowerCase();
  return REMOTE_INDICATORS.some((needle) => haystack.includes(needle));
}
