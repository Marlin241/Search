"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import {
  SearchCriteriaForm,
  EMPTY_SEARCH_CRITERIA_FORM_VALUE,
  toSearchCriteria,
  type SearchCriteriaFormValue,
} from "@/components/SearchCriteriaForm";
import { JobListingsList } from "@/components/JobListingsList";
import { SavedSearchPanel } from "@/components/SavedSearchPanel";
import { ApplicationCard } from "@/components/ApplicationCard";
import { ErrorBanner } from "@/components/ErrorBanner";
import { toBannerContent, isSessionExpired, type BannerContent } from "@/lib/errors";
import { searchJobs, createApplication } from "@/lib/api";
import { pollJobSearchDiscovery } from "@/lib/discoveryPolling";
import { useAuth } from "@/context/AuthContext";
import type { Application, JobListing, JobSearchResult } from "@/lib/types";

export default function CandidaturesPage() {
  return (
    <RequireAuth>
      <CandidaturesPageContent />
    </RequireAuth>
  );
}

function CandidaturesPageContent() {
  const { token, logout } = useAuth();
  const router = useRouter();
  const [criteria, setCriteria] = useState<SearchCriteriaFormValue>(EMPTY_SEARCH_CRITERIA_FORM_VALUE);
  const [searchResult, setSearchResult] = useState<JobSearchResult | null>(null);
  const [applications, setApplications] = useState<Application[]>([]);
  const [banner, setBanner] = useState<BannerContent | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const cancelPollRef = useRef<(() => void) | null>(null);

  function handleAuthError(error: unknown): boolean {
    if (isSessionExpired(error)) {
      logout();
      router.replace("/login");
      return true;
    }
    return false;
  }

  async function handleSearch() {
    if (!token) return;
    setBanner(null);
    setIsSearching(true);
    cancelPollRef.current?.();
    setIsDiscovering(false);
    try {
      const result = await searchJobs(token, toSearchCriteria(criteria));
      setSearchResult(result);
      if (result.discovery_pending) {
        setIsDiscovering(true);
        cancelPollRef.current = pollJobSearchDiscovery(
          token,
          result.search_id,
          (newListings) => {
            setSearchResult((prev) => (prev ? { ...prev, listings: [...prev.listings, ...newListings] } : prev));
          },
          () => setIsDiscovering(false)
        );
      }
    } catch (error) {
      if (!handleAuthError(error)) setBanner(toBannerContent(error));
    } finally {
      setIsSearching(false);
    }
  }

  async function handleCreateApplications(selected: JobListing[]) {
    if (!token) return;
    setBanner(null);
    setIsCreating(true);
    const created: Application[] = [];
    for (const listing of selected) {
      try {
        const application = await createApplication(token, {
          offer_url: listing.url,
          source: listing.source,
          company_name: listing.company,
          job_title: listing.title,
          ats_type: listing.ats_type,
        });
        created.push(application);
      } catch (error) {
        if (handleAuthError(error)) {
          setIsCreating(false);
          return;
        }
        setBanner(toBannerContent(error));
      }
    }
    setApplications((prev) => [...created, ...prev]);
    setIsCreating(false);
  }

  function handleApplicationUpdated(updated: Application) {
    setApplications((prev) => prev.map((application) => (application.id === updated.id ? updated : application)));
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-9 sm:px-8 sm:py-10">
      <div className="relative overflow-hidden rounded-[28px] bg-gradient-to-br from-accent2 to-accent2-strong px-7 py-7 text-[oklch(0.14_0.02_60)] sm:px-8">
        <p className="text-xs font-extrabold uppercase tracking-wide opacity-70">Candidatures</p>
        <h1 className="mt-1.5 font-display text-3xl font-extrabold tracking-tight">Trouver et postuler à des offres</h1>
        <p className="mt-1.5 max-w-md opacity-85">
          Définis tes critères, sélectionne les offres qui t&apos;intéressent, puis relis chaque candidature avant
          l&apos;envoi.
        </p>
      </div>

      <div className="mt-6">
        <SearchCriteriaForm value={criteria} onChange={setCriteria} onSearch={handleSearch} isSearching={isSearching} />
      </div>

      {token && (
        <div className="mt-3.5">
          <SavedSearchPanel token={token} criteria={criteria} />
        </div>
      )}

      {isDiscovering && (
        <p className="mt-3 text-sm text-ink-soft">Recherche en cours sur les sites des entreprises...</p>
      )}

      {banner && (
        <div className="mt-4">
          <ErrorBanner content={banner} />
        </div>
      )}

      {searchResult && (
        <div className="mt-6">
          <JobListingsList
            listings={searchResult.listings}
            unavailableSources={searchResult.unavailable_sources}
            onCreateApplications={handleCreateApplications}
            isCreating={isCreating}
          />
        </div>
      )}

      {applications.length > 0 && token && (
        <div className="mt-11 flex flex-col gap-5">
          <h2 className="font-display text-lg font-bold text-ink">Tes candidatures</h2>
          {applications.map((application) => (
            <ApplicationCard
              key={application.id}
              application={application}
              token={token}
              onUpdated={handleApplicationUpdated}
            />
          ))}
        </div>
      )}
    </main>
  );
}
