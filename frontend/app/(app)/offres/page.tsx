"use client";

import { useEffect, useMemo, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  MapPin,
  Building,
  Sparkles,
  SlidersHorizontal,
  ExternalLink,
  FolderKanban,
  Send,
  Loader2,
  Check,
  Bell,
  RefreshCw,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import {
  searchJobs,
  fetchJobSearchDiscovery,
  getCandidateProfile,
  getSavedSearch,
  saveSavedSearch,
  createApplication,
  openSavedJob,
} from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { LocationAutocomplete } from "@/components/common/LocationAutocomplete";
import { Select } from "@/components/ui/Select";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { Dialog } from "@/components/ui/Dialog";
import { CompatibilityBadge } from "@/components/jobs/CompatibilityBadge";
import { CompatibilityDetailModal } from "@/components/jobs/CompatibilityDetailModal";
import { SortControl, type SortOrder } from "@/components/jobs/SortControl";
import {
  cn,
  getInitials,
  sourceLabel,
} from "@/lib/utils";
import type {
  JobListing,
  SearchCriteria,
  SavedSearchOut,
} from "@/lib/types";

const CONTRACT_OPTIONS = [
  { value: "", label: "Tous types de contrat" },
  { value: "CDI", label: "CDI" },
  { value: "CDD", label: "CDD" },
  { value: "alternance", label: "Alternance" },
  { value: "stage", label: "Stage" },
  { value: "freelance", label: "Freelance" },
];

// Session-local cache of the last search: revisiting this page within the
// TTL redisplays results instantly with zero network calls, instead of
// re-hitting the backend (which itself caches upstream results for 15 min,
// but a round trip still costs a request + rate-limit slot). A manual
// search always overwrites this entry with fresh results.
//
// Keyed per user id, NOT a bare constant: sessionStorage survives a
// logout/login in the same tab (a normal flow on a shared device), so an
// unscoped key would silently hand the next account whoever-was-logged-in-
// before's search results and criteria on mount - a cross-user data leak.
const SEARCH_CACHE_TTL_MS = 15 * 60 * 1000;

function searchCacheKey(userId: number): string {
  return `offres-search-cache:${userId}`;
}

interface CachedSearch {
  keywords: string;
  location: string;
  contractType: string;
  remote: boolean;
  excludeKeywords: string;
  listings: JobListing[];
  savedAt: number;
}

function readSearchCache(userId: number): CachedSearch | null {
  try {
    const raw = sessionStorage.getItem(searchCacheKey(userId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedSearch;
    if (Date.now() - parsed.savedAt >= SEARCH_CACHE_TTL_MS) return null;
    return parsed;
  } catch {
    // Private browsing / storage disabled / corrupted entry: degrade to
    // "no cache" rather than breaking the page.
    return null;
  }
}

function writeSearchCache(userId: number, entry: CachedSearch): void {
  try {
    sessionStorage.setItem(searchCacheKey(userId), JSON.stringify(entry));
  } catch {
    // ignore - see readSearchCache
  }
}

export default function OffresPage() {
  const { token, user } = useAuth();
  const router = useRouter();
  const [openingWorkspaceUrl, setOpeningWorkspaceUrl] = useState<string | null>(null);

  const handleOpenWorkspace = async (job: JobListing) => {
    if (!token) return;
    setOpeningWorkspaceUrl(job.url);
    try {
      const saved = await openSavedJob(token, {
        offer_url: job.url,
        title: job.title,
        company: job.company,
        location: job.location,
        snippet: job.snippet,
        source: job.source,
        ats_type: job.ats_type,
        salary: job.salary ?? null,
      });
      router.push(`/offres/${saved.id}`);
    } catch (err: any) {
      console.error("Failed to open workspace:", err);
      toast.error(err?.detail || "Impossible d'ouvrir l'espace de travail.");
    } finally {
      setOpeningWorkspaceUrl(null);
    }
  };

  // Search state
  const [keywords, setKeywords] = useState("");
  const [location, setLocation] = useState("");
  const [contractType, setContractType] = useState("");
  const [remote, setRemote] = useState(false);
  const [excludeKeywords, setExcludeKeywords] = useState("");

  const [listings, setListings] = useState<JobListing[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [searchId, setSearchId] = useState<string | null>(null);
  const [discoveryPending, setDiscoveryPending] = useState(false);
  const [sortOrder, setSortOrder] = useState<SortOrder>("compatibility");
  const [compatibilityModalJob, setCompatibilityModalJob] = useState<JobListing | null>(null);
  const [cacheInfo, setCacheInfo] = useState<{ savedAt: number } | null>(null);

  const sortedListings = useMemo(() => {
    if (sortOrder === "compatibility") return listings;
    // "recent": listings without a posted_at sink to the bottom rather than
    // being treated as oldest, since missing data isn't the same as "old".
    return [...listings].sort((a, b) => {
      if (!a.posted_at && !b.posted_at) return 0;
      if (!a.posted_at) return 1;
      if (!b.posted_at) return -1;
      return new Date(b.posted_at).getTime() - new Date(a.posted_at).getTime();
    });
  }, [listings, sortOrder]);

  // Selection & batch apply
  const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());
  const [isApplying, setIsApplying] = useState(false);
  const [applyProgress, setApplyProgress] = useState<{ current: number; total: number } | null>(null);

  // Saved search alert
  const [isAlertModalOpen, setIsAlertModalOpen] = useState(false);
  const [savedSearch, setSavedSearch] = useState<SavedSearchOut | null>(null);
  const [alertKeywords, setAlertKeywords] = useState("");
  const [alertLocation, setAlertLocation] = useState("");
  const [alertEnabled, setAlertEnabled] = useState(true);
  const [isSavingAlert, setIsSavingAlert] = useState(false);

  // Poll discovery
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!token) return;
    getSavedSearch(token)
      .then((res) => {
        setSavedSearch(res);
        setAlertKeywords(res.keywords);
        setAlertLocation(res.location || "");
        setAlertEnabled(res.enabled);
      })
      .catch(() => {});
  }, [token]);

  useEffect(() => {
    if (!token || !searchId || !discoveryPending) return;

    pollingRef.current = setInterval(async () => {
      try {
        const res = await fetchJobSearchDiscovery(token, searchId);
        if (res.new_listings.length > 0) {
          setListings((prev) => {
            const merged = [...prev, ...res.new_listings];
            // Keep the session cache's listings in sync with late-arriving
            // discovery results too, without touching savedAt (this must
            // not extend the cache's own 15 min lifetime).
            try {
              if (user) {
                const key = searchCacheKey(user.id);
                const raw = sessionStorage.getItem(key);
                if (raw) {
                  const cached = JSON.parse(raw) as CachedSearch;
                  sessionStorage.setItem(
                    key,
                    JSON.stringify({ ...cached, listings: merged })
                  );
                }
              }
            } catch {
              // ignore
            }
            return merged;
          });
        }
        if (res.done) {
          setDiscoveryPending(false);
          if (pollingRef.current) clearInterval(pollingRef.current);
        }
      } catch {
        setDiscoveryPending(false);
        if (pollingRef.current) clearInterval(pollingRef.current);
      }
    }, 3000);

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [token, user, searchId, discoveryPending]);

  const runSearch = async (searchKeywords: string, searchLocation: string) => {
    if (!token || !user || !searchKeywords.trim()) return;

    setIsSearching(true);
    setSelectedUrls(new Set());
    setCacheInfo(null);

    const trimmedKeywords = searchKeywords.trim();
    const trimmedLocation = searchLocation.trim();
    const criteria: SearchCriteria = {
      keywords: trimmedKeywords,
      location: trimmedLocation || undefined,
      contract_type: contractType || undefined,
      remote: remote || undefined,
      exclude_keywords: excludeKeywords
        ? excludeKeywords.split(",").map((s) => s.trim()).filter(Boolean)
        : [],
    };

    try {
      const res = await searchJobs(token, criteria);
      setListings(res.listings || []);
      setHasSearched(true);
      setSearchId(res.search_id);
      setDiscoveryPending(res.discovery_pending);
      writeSearchCache(user.id, {
        keywords: trimmedKeywords,
        location: trimmedLocation,
        contractType,
        remote,
        excludeKeywords,
        listings: res.listings || [],
        savedAt: Date.now(),
      });
    } catch (err) {
      console.error("Job search error:", err);
      toast.error(
        err instanceof Error
          ? err.message
          : "La recherche a échoué. Réessaie dans un instant."
      );
    } finally {
      setIsSearching(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    await runSearch(keywords, location);
  };

  // On arrival, first try to restore the last search from this session's
  // cache - instant, zero network calls at all. Only when there's no valid
  // (unexpired) cache entry do we fall back to prefilling from the
  // profile's declared preferences and searching automatically - a
  // starting point, not a lock: the form stays fully editable either way.
  useEffect(() => {
    if (!token || !user) return;

    const cached = readSearchCache(user.id);
    if (cached) {
      setKeywords(cached.keywords);
      setLocation(cached.location);
      setContractType(cached.contractType);
      setRemote(cached.remote);
      setExcludeKeywords(cached.excludeKeywords);
      setListings(cached.listings);
      setHasSearched(true);
      setCacheInfo({ savedAt: cached.savedAt });
      return;
    }

    if (keywords.trim()) return;
    getCandidateProfile(token)
      .then((profile) => {
        const firstTitle = profile.desired_job_titles?.[0];
        if (!firstTitle) return;
        const firstLocation = profile.desired_locations?.[0] ?? "";
        setKeywords(firstTitle);
        setLocation(firstLocation);
        runSearch(firstTitle, firstLocation);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, user]);

  const toggleSelect = (url: string) => {
    setSelectedUrls((prev) => {
      const next = new Set(prev);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });
  };

  const selectAll = () => {
    if (selectedUrls.size === listings.length) {
      setSelectedUrls(new Set());
    } else {
      setSelectedUrls(new Set(listings.map((l) => l.url)));
    }
  };

  const handleBatchApply = async () => {
    if (!token || selectedUrls.size === 0) return;

    const selectedListings = listings.filter((l) => selectedUrls.has(l.url));
    setIsApplying(true);
    setApplyProgress({ current: 0, total: selectedListings.length });

    for (let i = 0; i < selectedListings.length; i++) {
      const item = selectedListings[i];
      try {
        await createApplication(token, {
          offer_url: item.url,
          company_name: item.company,
          job_title: item.title,
          source: item.source,
          ats_type: item.ats_type,
        });
      } catch (err) {
        console.error(`Failed to apply to ${item.title}:`, err);
      }
      setApplyProgress({ current: i + 1, total: selectedListings.length });
    }

    setIsApplying(false);
    setSelectedUrls(new Set());
    setApplyProgress(null);
  };

  const handleSaveAlert = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !alertKeywords.trim()) return;

    setIsSavingAlert(true);
    try {
      const saved = await saveSavedSearch(token, {
        keywords: alertKeywords.trim(),
        location: alertLocation.trim() || null,
        enabled: alertEnabled,
        // Fuseau réel de l'utilisateur plutôt que le défaut serveur
        // (Europe/Paris jusqu'ici, sans rapport avec sa localisation réelle).
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      });
      setSavedSearch(saved);
      setIsAlertModalOpen(false);
    } catch (err) {
      console.error("Failed to save alert:", err);
    } finally {
      setIsSavingAlert(false);
    }
  };

  // Job detail modal state
  const [selectedModalJob, setSelectedModalJob] = useState<JobListing | null>(null);

  // Extract salary heuristic if present in snippet or title
  const extractSalary = (text: string): string | null => {
    const match = text.match(/(\d{2,3}[\s.]?[kK]€|\d{2,3}\s?000\s?€|\d{2,3}[-\s]\d{2,3}\s?[kK]€|\d{2,3}\s?000\s?-\s?\d{2,3}\s?000\s?€|\d+[\s.]?\d*\s?€\s?\/?\s?(mois|an|heure))/i);
    return match ? match[0] : null;
  };

  return (
    <div className="space-y-6 animate-fade-in pb-16">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-display font-bold text-foreground">
            Offres d'emploi
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Recherchez parmi des milliers d'offres centralisées et postulez en 1 clic.
          </p>
        </div>

        <Button
          variant={savedSearch?.enabled ? "secondary" : "outline"}
          size="sm"
          icon={<Bell className="w-4 h-4" />}
          onClick={() => setIsAlertModalOpen(true)}
        >
          {savedSearch?.enabled ? "Alerte active" : "Créer une alerte quotidienne"}
        </Button>
      </div>

      {/* Search Form Card */}
      <Card>
        <CardContent className="p-5">
          <form onSubmit={handleSearch} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <Input
                label="Intitulé ou mot-clé"
                placeholder="ex: Product Manager, React..."
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                required
                icon={<Search className="w-4 h-4" />}
              />
              <LocationAutocomplete value={location} onChange={setLocation} />
              <Select
                label="Type de contrat"
                options={CONTRACT_OPTIONS}
                value={contractType}
                onChange={(e) => setContractType(e.target.value)}
              />
              <Input
                label="Exclure des mots-clés"
                placeholder="ex: Stage, Junior (séparés par virgule)"
                value={excludeKeywords}
                onChange={(e) => setExcludeKeywords(e.target.value)}
              />
            </div>

            <div className="flex items-center justify-between pt-2">
              <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-muted-foreground">
                <input
                  type="checkbox"
                  checked={remote}
                  onChange={(e) => setRemote(e.target.checked)}
                  className="rounded border-input text-primary focus:ring-primary h-4 w-4"
                />
                <span>Télétravail uniquement</span>
              </label>

              <Button
                type="submit"
                variant="primary"
                isLoading={isSearching}
                icon={<Search className="w-4 h-4" />}
              >
                Rechercher les offres
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Cached results banner */}
      {cacheInfo && (
        <div className="flex items-center justify-between gap-3 p-3 bg-muted/40 border border-border/60 rounded-xl text-xs text-muted-foreground">
          <span>
            Résultats du cache — actualisés il y a{" "}
            {Math.max(1, Math.round((Date.now() - cacheInfo.savedAt) / 60000))} min
          </span>
          <button
            type="button"
            onClick={() => runSearch(keywords, location)}
            className="flex items-center gap-1.5 font-semibold text-primary hover:underline shrink-0"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Actualiser
          </button>
        </div>
      )}

      {/* Results Section */}
      <div className="space-y-4">
        {listings.length > 0 && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-1">
            <div className="flex items-center justify-between sm:justify-start gap-4">
              <span className="text-xs font-semibold text-muted-foreground">
                {listings.length} opportunité{listings.length > 1 ? "s" : ""} trouvée{listings.length > 1 ? "s" : ""}
              </span>
              <button
                onClick={selectAll}
                className="text-xs font-medium text-primary hover:underline"
              >
                {selectedUrls.size === listings.length
                  ? "Tout désélectionner"
                  : "Tout sélectionner"}
              </button>
            </div>
            <SortControl value={sortOrder} onChange={setSortOrder} />
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {isSearching ? (
            Array.from({ length: 6 }).map((_, i) => (
              <Card key={i} className="p-5">
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <Skeleton className="w-10 h-10 rounded-xl" />
                    <div className="space-y-1.5 flex-1">
                      <Skeleton className="h-4 w-2/3" />
                      <Skeleton className="h-3 w-1/3" />
                    </div>
                  </div>
                  <Skeleton className="h-12 w-full" />
                </div>
              </Card>
            ))
          ) : sortedListings.length > 0 ? (
            sortedListings.map((job, idx) => {
              const isSelected = selectedUrls.has(job.url);
              const salaryHint =
                job.salary || extractSalary(job.snippet || "") || extractSalary(job.title || "");
              return (
                <Card
                  key={job.url + idx}
                  className={cn(
                    "relative transition-all p-5 cursor-pointer group",
                    isSelected
                      ? "border-primary bg-primary/[0.03] shadow-lift"
                      : "hover:border-primary/50 hover:shadow-card"
                  )}
                  onClick={() => setSelectedModalJob(job)}
                >
                  <div className="flex items-start justify-between gap-3">
                    {/* Checkbox */}
                    <div
                      onClick={(e) => e.stopPropagation()}
                      className="pt-0.5"
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelect(job.url)}
                        className="h-4 w-4 rounded border-input text-primary focus:ring-primary shrink-0 cursor-pointer"
                      />
                    </div>

                    {/* Job Details */}
                    <div className="flex-1 min-w-0 space-y-2">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary font-bold text-xs flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                          {getInitials(job.company)}
                        </div>
                        <div className="min-w-0">
                          <h3 className="text-sm font-bold text-foreground truncate group-hover:text-primary transition-colors">
                            {job.title}
                          </h3>
                          <p className="text-xs text-muted-foreground truncate">
                            {job.company}
                          </p>
                        </div>
                      </div>

                      {/* Meta badges */}
                      <div className="flex flex-wrap items-center gap-2 pt-0.5">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setCompatibilityModalJob(job);
                          }}
                        >
                          <CompatibilityBadge score={job.compatibility_score} />
                        </button>
                        {job.location && (
                          <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                            <MapPin className="w-3 h-3 text-muted-foreground/80" />
                            {job.location}
                          </span>
                        )}
                        {salaryHint && (
                          <Badge variant="success">{salaryHint}</Badge>
                        )}
                        <Badge variant="outline">{sourceLabel(job.source)}</Badge>
                        {job.is_remote && (
                          <Badge variant="accent">Remote</Badge>
                        )}
                        {job.ats_type && (
                          <Badge variant="accent">ATS : {job.ats_type}</Badge>
                        )}
                      </div>

                      {/* Snippet */}
                      {job.snippet && (
                        <p className="text-xs text-muted-foreground/80 line-clamp-2 pt-1">
                          {job.snippet}
                        </p>
                      )}

                      <div className="pt-1 flex items-center gap-2 text-[11px] font-semibold text-primary">
                        <span>Voir la fiche détaillée & postuler</span>
                        <span className="text-xs">→</span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex flex-col items-center gap-1 shrink-0">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenWorkspace(job);
                        }}
                        disabled={openingWorkspaceUrl === job.url}
                        className="p-1.5 text-muted-foreground hover:text-primary transition-colors rounded-lg hover:bg-muted disabled:opacity-50"
                        title="Ouvrir dans l'espace de travail"
                      >
                        {openingWorkspaceUrl === job.url ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <FolderKanban className="w-4 h-4" />
                        )}
                      </button>
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="p-1.5 text-muted-foreground hover:text-primary transition-colors rounded-lg hover:bg-muted"
                        title="Ouvrir l'offre originale"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    </div>
                  </div>
                </Card>
              );
            })
          ) : (
            <div className="col-span-full">
              <EmptyState
                icon={Search}
                title={
                  hasSearched
                    ? "Aucune offre pour cette recherche"
                    : "Prêt à lancer votre recherche ?"
                }
                description={
                  hasSearched
                    ? "Essaie d'élargir la zone, de retirer un filtre ou de changer de mots-clés."
                    : "Indiquez vos mots-clés et votre ville ci-dessus pour afficher les meilleures offres disponibles."
                }
              />
            </div>
          )}
        </div>
      </div>

      {/* Detail Modal for Job Offer */}
      <Dialog
        isOpen={!!selectedModalJob}
        onClose={() => setSelectedModalJob(null)}
        title={selectedModalJob?.title || "Détails de l'offre"}
        description={selectedModalJob ? `${selectedModalJob.company} · Source : ${sourceLabel(selectedModalJob.source)}` : ""}
        className="max-w-2xl"
      >
        {selectedModalJob && (
          <div className="space-y-5 mt-2 max-h-[75vh] overflow-y-auto pr-1">
            {/* Highlights Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-3.5 bg-muted/40 rounded-xl border border-border/60 text-xs">
              <div>
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Entreprise</span>
                <span className="font-bold text-foreground">{selectedModalJob.company}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Localisation</span>
                <span className="font-bold text-foreground">
                  {selectedModalJob.location || "Non précisée"}
                  {selectedModalJob.is_remote && " · Remote"}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Source</span>
                <span className="font-bold text-primary">{sourceLabel(selectedModalJob.source)}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Plateforme ATS</span>
                <span className="font-semibold text-foreground">{selectedModalJob.ats_type ? selectedModalJob.ats_type.toUpperCase() : "Standard"}</span>
              </div>
              <div className="col-span-2">
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">
                  {selectedModalJob.salary ? "Rémunération" : "Rémunération estimée"}
                </span>
                <span className="font-bold text-success">
                  {selectedModalJob.salary ||
                    extractSalary(selectedModalJob.snippet || "") ||
                    extractSalary(selectedModalJob.title || "") ||
                    "Non précisée par l'employeur"}
                </span>
              </div>
            </div>

            {/* Description / Snippet */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Description & Compétences requises
              </h4>
              <div className="p-4 rounded-xl bg-card border border-border text-xs leading-relaxed text-foreground whitespace-pre-line">
                {selectedModalJob.snippet ? selectedModalJob.snippet : "Aucun extrait textuel disponible pour cette offre. Cliquez sur le lien ci-dessous pour consulter l'intégralité du poste."}
              </div>
            </div>

            {/* Modal actions */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-4 border-t border-border">
              <a
                href={selectedModalJob.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground font-medium"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                Consulter sur {sourceLabel(selectedModalJob.source)}
              </a>

              <div className="flex items-center gap-2 w-full sm:w-auto">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedModalJob(null)}
                >
                  Fermer
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  isLoading={openingWorkspaceUrl === selectedModalJob.url}
                  icon={<FolderKanban className="w-3.5 h-3.5" />}
                  onClick={() => handleOpenWorkspace(selectedModalJob)}
                >
                  Ouvrir l'espace de travail
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  icon={<Send className="w-3.5 h-3.5" />}
                  onClick={async () => {
                    if (!token || !selectedModalJob) return;
                    try {
                      await createApplication(token, {
                        offer_url: selectedModalJob.url,
                        company_name: selectedModalJob.company,
                        job_title: selectedModalJob.title,
                        source: selectedModalJob.source,
                        ats_type: selectedModalJob.ats_type,
                        offer_text: selectedModalJob.snippet,
                      });
                      setSelectedModalJob(null);
                      toast.success(
                        "Candidature créée avec succès ! Retrouvez-la dans votre suivi."
                      );
                    } catch (err: any) {
                      toast.error(err?.detail || "Erreur lors de la création de la candidature.");
                    }
                  }}
                >
                  Postuler à cette offre
                </Button>
              </div>
            </div>
          </div>
        )}
      </Dialog>

      {/* Compatibility Detail Modal */}
      <CompatibilityDetailModal
        listing={compatibilityModalJob}
        token={token}
        onClose={() => setCompatibilityModalJob(null)}
      />

      {/* Sticky batch apply bottom bar */}
      <AnimatePresence>
        {selectedUrls.size > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 30 }}
            className="fixed bottom-20 lg:bottom-6 left-1/2 -translate-x-1/2 z-40 w-[90%] max-w-xl bg-card border border-border shadow-lift rounded-2xl p-4 flex items-center justify-between gap-4 backdrop-blur-xl"
          >
            <div className="text-xs font-semibold">
              <span className="text-primary font-bold">{selectedUrls.size}</span> offre{selectedUrls.size > 1 ? "s" : ""} sélectionnée{selectedUrls.size > 1 ? "s" : ""}
            </div>

            <Button
              variant="primary"
              size="sm"
              isLoading={isApplying}
              onClick={handleBatchApply}
              icon={<Send className="w-3.5 h-3.5" />}
            >
              {isApplying
                ? `Candidature ${applyProgress?.current || 0}/${applyProgress?.total || 0}...`
                : "Postuler en lot"}
            </Button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Saved Search Modal */}
      <Dialog
        isOpen={isAlertModalOpen}
        onClose={() => setIsAlertModalOpen(false)}
        title="Alerte quotidienne d'offres"
        description="Recevez chaque matin par email les nouvelles opportunités correspondant à vos critères."
      >
        <form onSubmit={handleSaveAlert} className="space-y-4 mt-4">
          <Input
            label="Mots-clés recherchés"
            placeholder="ex: Tech Lead, Product Manager"
            value={alertKeywords}
            onChange={(e) => setAlertKeywords(e.target.value)}
            required
          />
          <LocationAutocomplete
            value={alertLocation}
            onChange={setAlertLocation}
            id="alert-location-autocomplete"
          />

          <label className="flex items-center gap-2 cursor-pointer text-xs font-medium">
            <input
              type="checkbox"
              checked={alertEnabled}
              onChange={(e) => setAlertEnabled(e.target.checked)}
              className="rounded border-input text-primary focus:ring-primary h-4 w-4"
            />
            <span>Activer les alertes par email</span>
          </label>

          <div className="flex justify-end gap-2 pt-3">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setIsAlertModalOpen(false)}
            >
              Annuler
            </Button>
            <Button type="submit" variant="primary" isLoading={isSavingAlert}>
              Enregistrer l'alerte
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
