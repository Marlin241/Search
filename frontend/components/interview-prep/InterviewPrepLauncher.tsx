"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Textarea";
import { PersonaCards, INTERVIEW_PERSONAS } from "@/components/interview-prep/PersonaCards";
import { WebSearchToggle } from "@/components/interview-prep/WebSearchToggle";
import type { InterviewPrepRequestIn } from "@/lib/types";

export function InterviewPrepLauncher({
  isLaunching,
  onLaunch,
}: {
  isLaunching: boolean;
  onLaunch: (payload: InterviewPrepRequestIn) => void;
}) {
  const [persona, setPersona] = useState<string>(INTERVIEW_PERSONAS[0].value);
  const [extraContext, setExtraContext] = useState("");
  const [useWebSearch, setUseWebSearch] = useState(false);

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Qui te reçoit en entretien ?
        </label>
        <PersonaCards value={persona} onChange={setPersona} />
      </div>

      <Textarea
        label="Contexte additionnel (optionnel)"
        placeholder="Ex : deuxième entretien, poste ouvert suite à une réorganisation..."
        value={extraContext}
        onChange={(e) => setExtraContext(e.target.value)}
        rows={3}
      />

      <WebSearchToggle checked={useWebSearch} onChange={setUseWebSearch} />

      <Button
        variant="primary"
        fullWidth
        isLoading={isLaunching}
        icon={<Sparkles className="w-4 h-4" />}
        onClick={() =>
          onLaunch({
            persona,
            extra_context: extraContext.trim() || null,
            use_web_search: useWebSearch,
          })
        }
      >
        Générer mon dossier de préparation
      </Button>
    </div>
  );
}
