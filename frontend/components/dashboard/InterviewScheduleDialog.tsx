"use client";

import { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { createInterview } from "@/lib/api";
import { INTERVIEW_TYPE_LABELS } from "@/components/dashboard/CalendarLegend";
import type { ApplicationOut, InterviewType } from "@/lib/types";

const TYPE_OPTIONS = (Object.keys(INTERVIEW_TYPE_LABELS) as InterviewType[]).map((value) => ({
  value,
  label: INTERVIEW_TYPE_LABELS[value],
}));

export function InterviewScheduleDialog({
  application,
  token,
  isOpen,
  onClose,
  onScheduled,
}: {
  application: ApplicationOut;
  token: string;
  isOpen: boolean;
  onClose: () => void;
  onScheduled: () => void;
}) {
  const [scheduledAt, setScheduledAt] = useState("");
  const [interviewType, setInterviewType] = useState<InterviewType>("rh");
  const [locationOrLink, setLocationOrLink] = useState("");
  const [notes, setNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!scheduledAt) {
      setError("Choisissez une date et une heure.");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      await createInterview(token, application.id, {
        scheduled_at: new Date(scheduledAt).toISOString(),
        interview_type: interviewType,
        location_or_link: locationOrLink || null,
        notes: notes || null,
      });
      setScheduledAt("");
      setLocationOrLink("");
      setNotes("");
      onScheduled();
      onClose();
    } catch (err: any) {
      setError(err?.detail || "Erreur lors de la planification.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Planifier un entretien"
      description={`${application.job_title} chez ${application.company_name}`}
    >
      <div className="space-y-4 mt-2">
        <Input
          label="Date et heure"
          type="datetime-local"
          required
          value={scheduledAt}
          onChange={(e) => setScheduledAt(e.target.value)}
        />
        <Select
          label="Type d'entretien"
          options={TYPE_OPTIONS}
          value={interviewType}
          onChange={(e) => setInterviewType(e.target.value as InterviewType)}
        />
        <Input
          label="Lieu ou lien"
          placeholder="Visio, adresse..."
          value={locationOrLink}
          onChange={(e) => setLocationOrLink(e.target.value)}
        />
        <Textarea
          label="Notes"
          placeholder="Points à préparer, interlocuteurs..."
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
        {error && <p className="text-xs font-medium text-destructive">{error}</p>}
        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Annuler
          </Button>
          <Button variant="primary" size="sm" isLoading={isSaving} onClick={handleSubmit}>
            Planifier
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
