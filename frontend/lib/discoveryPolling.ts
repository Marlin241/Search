import { fetchJobSearchDiscovery } from "./api";
import type { JobListing } from "./types";

export function pollJobSearchDiscovery(
  token: string,
  searchId: string,
  onNewListings: (listings: JobListing[]) => void,
  onDone: () => void,
  intervalMs: number = 3000
): () => void {
  const intervalId = setInterval(async () => {
    try {
      const result = await fetchJobSearchDiscovery(token, searchId);
      if (result.new_listings.length > 0) onNewListings(result.new_listings);
      if (result.done) {
        clearInterval(intervalId);
        onDone();
      }
    } catch {
      clearInterval(intervalId);
      onDone();
    }
  }, intervalMs);

  return () => clearInterval(intervalId);
}
