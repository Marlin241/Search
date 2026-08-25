import { Newspaper } from "lucide-react";
import { AIProgressChecklist } from "@/components/generation/AIProgressChecklist";
import { CompanyFactsCard } from "@/components/interview-prep/CompanyFactsCard";
import { ProbableQuestionsList } from "@/components/interview-prep/ProbableQuestionsList";
import { PracticalExercises } from "@/components/interview-prep/PracticalExercises";
import { CoachingChecklist } from "@/components/interview-prep/CoachingChecklist";
import type { GenerationJobOut, InterviewPrepDossierOut } from "@/lib/types";

export function DossierViewProgress({
  job,
  useWebSearch,
}: {
  job: GenerationJobOut<null>;
  useWebSearch: boolean;
}) {
  const steps = useWebSearch
    ? [
        "Analyse du profil et de l'offre",
        "Recherche des actualités",
        "Rédaction du dossier",
        "Finalisation",
      ]
    : ["Analyse du profil et de l'offre", "Rédaction du dossier", "Finalisation"];

  return (
    <AIProgressChecklist steps={steps} currentStepIndex={job.step_index} status={job.status} />
  );
}

export function DossierView({ dossier }: { dossier: InterviewPrepDossierOut }) {
  const content = dossier.dossier;

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-primary/30 bg-primary/5 p-4">
        <p className="text-sm font-semibold text-foreground">{content.narrative_angle}</p>
      </div>

      <CompanyFactsCard facts={content.company_facts} />

      {content.recent_news.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-bold text-foreground flex items-center gap-1.5">
            <Newspaper className="w-4 h-4" /> Actualités récentes
          </h4>
          <ul className="space-y-2">
            {content.recent_news.map((news, i) => (
              <li key={i} className="rounded-xl border border-border p-3">
                <p className="text-sm font-semibold text-foreground">{news.headline}</p>
                <p className="text-xs text-muted-foreground mt-1">{news.summary}</p>
                {news.source_url && (
                  <a
                    href={news.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-primary hover:underline mt-1 inline-block"
                  >
                    Source
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="space-y-2">
        <h4 className="text-sm font-bold text-foreground">Questions probables</h4>
        <ProbableQuestionsList questions={content.probable_questions} />
      </div>

      <div className="space-y-2">
        <h4 className="text-sm font-bold text-foreground">Exercices pratiques</h4>
        <PracticalExercises exercises={content.practical_exercises} />
      </div>

      <div className="space-y-2">
        <h4 className="text-sm font-bold text-foreground">Checklist de coaching</h4>
        <CoachingChecklist checklist={content.coaching_checklist} />
      </div>
    </div>
  );
}
