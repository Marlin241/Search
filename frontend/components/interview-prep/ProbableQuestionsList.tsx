import { Target } from "lucide-react";
import type { ProbableQuestion } from "@/lib/types";

export function ProbableQuestionsList({ questions }: { questions: ProbableQuestion[] }) {
  if (questions.length === 0) {
    return <p className="text-xs text-muted-foreground">Aucune question générée.</p>;
  }

  return (
    <ul className="space-y-3">
      {questions.map((q, i) => (
        <li key={i} className="rounded-xl border border-border p-4 space-y-2">
          <p className="text-sm font-bold text-foreground">{q.question}</p>
          {q.targets_weak_point && (
            <div className="inline-flex items-center gap-1.5 rounded-full bg-accent/15 text-accent-foreground border border-accent/30 px-2 py-0.5 text-xs font-medium">
              <Target className="w-3 h-3" />
              Cible : {q.targets_weak_point}
            </div>
          )}
          <p className="text-xs text-muted-foreground leading-relaxed">{q.model_answer}</p>
        </li>
      ))}
    </ul>
  );
}
