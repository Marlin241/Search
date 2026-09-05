import type { CompatibilityDetailOut } from "@/lib/types";

/**
 * Persists compatibility-detail results across page reloads (localStorage,
 * not a module-level Map) so the same offer never re-triggers a paid LLM
 * call just because the user closed and reopened the modal or refreshed the
 * page. Cleared only on logout (see AuthContext) - never on its own.
 */
const STORAGE_KEY = "search_compatibility_cache";
const MAX_ENTRIES = 300;

type CacheShape = Record<string, CompatibilityDetailOut>;

function readCache(): CacheShape {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as CacheShape) : {};
  } catch {
    return {};
  }
}

function writeCache(cache: CacheShape) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cache));
  } catch {
    // Storage unavailable (private mode, quota...) - the cache is a
    // best-effort optimization, never a requirement.
  }
}

export function getCachedCompatibilityDetail(
  offerUrl: string
): CompatibilityDetailOut | null {
  return readCache()[offerUrl] ?? null;
}

export function setCachedCompatibilityDetail(
  offerUrl: string,
  detail: CompatibilityDetailOut
) {
  const cache = readCache();
  cache[offerUrl] = detail;
  const keys = Object.keys(cache);
  if (keys.length > MAX_ENTRIES) {
    // Insertion order in a plain object follows string-key insertion order
    // in every engine this app targets - drop the oldest entries first.
    for (const staleKey of keys.slice(0, keys.length - MAX_ENTRIES)) {
      delete cache[staleKey];
    }
  }
  writeCache(cache);
}

export function clearCompatibilityCache() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // best-effort
  }
}
