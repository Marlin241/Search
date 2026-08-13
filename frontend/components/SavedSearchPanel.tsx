"use client";

import { useEffect, useState } from "react";
import { Card } from "./ui/Card";
import { Button } from "./ui/Button";
import { Select } from "./ui/Field";
import { ErrorBanner } from "./ErrorBanner";
import { getSavedSearch, saveSavedSearch } from "@/lib/api";
import { toBannerContent, type BannerContent } from "@/lib/errors";
import { toSearchCriteria, type SearchCriteriaFormValue } from "./SearchCriteriaForm";

const TIMEZONES = [
  "Europe/Paris",
  "Europe/London",
  "America/New_York",
  "America/Los_Angeles",
  "Africa/Dakar",
  "UTC",
];

interface SavedSearchPanelProps {
  token: string;
  criteria: SearchCriteriaFormValue;
}

export function SavedSearchPanel({ token, criteria }: SavedSearchPanelProps) {
  const [timezone, setTimezone] = useState("Europe/Paris");
  const [enabled, setEnabled] = useState(false);
  const [hasSaved, setHasSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [banner, setBanner] = useState<BannerContent | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSavedSearch(token).then((saved) => {
      if (cancelled || !saved) return;
      setTimezone(saved.timezone);
      setEnabled(saved.enabled);
      setHasSaved(true);
    });
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function persist(nextEnabled: boolean) {
    setBanner(null);
    setIsSaving(true);
    try {
      const saved = await saveSavedSearch(token, {
        ...toSearchCriteria(criteria),
        timezone,
        enabled: nextEnabled,
      });
      setEnabled(saved.enabled);
      setHasSaved(true);
    } catch (error) {
      setBanner(toBannerContent(error));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Card className="mt-4 flex flex-col gap-3 p-4">
      <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">Recherche automatique</p>
      <p className="text-sm text-slate-600 dark:text-slate-400">
        Recevez un email quotidien listant les nouvelles offres correspondant aux critères ci-dessus.
      </p>
      <label className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-300">
        Fuseau horaire
        <Select value={timezone} onChange={(event) => setTimezone(event.target.value)}>
          {TIMEZONES.map((tz) => (
            <option key={tz} value={tz}>
              {tz}
            </option>
          ))}
        </Select>
      </label>
      {banner && <ErrorBanner content={banner} />}
      <div className="flex items-center gap-3">
        <Button
          onClick={() => persist(true)}
          isLoading={isSaving}
          disabled={criteria.keywords.trim().length === 0}
          className="w-fit"
        >
          Sauvegarder cette recherche
        </Button>
        {hasSaved && (
          <Button variant="secondary" onClick={() => persist(!enabled)} isLoading={isSaving} className="w-fit">
            {enabled ? "Désactiver" : "Activer"}
          </Button>
        )}
      </div>
    </Card>
  );
}
