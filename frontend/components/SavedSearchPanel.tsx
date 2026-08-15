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
    <Card className="mt-3.5 flex flex-col gap-2.5 p-5">
      <p className="text-[14.5px] font-bold text-ink">Recherche automatique</p>
      <p className="text-[13.5px] text-ink-soft">
        Reçois un email dès qu&apos;une nouvelle offre correspond à ces critères.
      </p>
      <label className="flex flex-col gap-1.5 text-[13px] font-semibold text-ink-soft">
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
      <div className="flex items-center gap-2.5">
        <Button
          onClick={() => persist(true)}
          isLoading={isSaving}
          disabled={criteria.keywords.trim().length === 0}
          variant="secondary"
          size="sm"
          className="w-fit"
        >
          Sauvegarder cette recherche
        </Button>
        {hasSaved && (
          <Button variant="secondary" size="sm" onClick={() => persist(!enabled)} isLoading={isSaving} className="w-fit">
            {enabled ? "Désactiver" : "Activer"}
          </Button>
        )}
      </div>
    </Card>
  );
}
