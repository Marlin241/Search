"use client";

import { Mail } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { LetterGenerationPanel } from "@/components/generation/LetterGenerationPanel";
import type { SavedJobOut } from "@/lib/types";

export function LettreTab({
  savedJob,
  token,
  onGoToCvTab,
}: {
  savedJob: SavedJobOut;
  token: string;
  onGoToCvTab: () => void;
}) {
  const diagnosticId = savedJob.latest_diagnostic?.id;
  const existingLetter = savedJob.documents.find((doc) => doc.kind === "lettre");

  if (!diagnosticId) {
    return (
      <Card>
        <CardContent className="p-6">
          <EmptyState
            icon={Mail}
            title="Diagnostic requis"
            description="Lancez d'abord un diagnostic ATS dans l'onglet CV pour pouvoir générer une lettre de motivation sur-mesure."
            action={
              <Button variant="primary" size="sm" onClick={onGoToCvTab}>
                Aller à l'onglet CV
              </Button>
            }
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <LetterGenerationPanel
      diagnosticId={diagnosticId}
      existingLetter={existingLetter}
      token={token}
    />
  );
}
