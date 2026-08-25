import { Badge } from "@/components/ui/Badge";
import type { PracticalExercise } from "@/lib/types";

const DIFFICULTY_VARIANT: Record<PracticalExercise["difficulty"], "success" | "warning" | "destructive"> = {
  facile: "success",
  moyen: "warning",
  difficile: "destructive",
};

export function PracticalExercises({ exercises }: { exercises: PracticalExercise[] }) {
  if (exercises.length === 0) {
    return <p className="text-xs text-muted-foreground">Aucun exercice généré.</p>;
  }

  return (
    <ul className="space-y-3">
      {exercises.map((exercise, i) => (
        <li key={i} className="rounded-xl border border-border p-4 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-bold text-foreground">{exercise.title}</p>
            <Badge variant={DIFFICULTY_VARIANT[exercise.difficulty]} size="sm">
              {exercise.difficulty}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">{exercise.prompt}</p>
          {exercise.pitfalls_to_avoid.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-destructive">
                Pièges à éviter
              </p>
              <ul className="mt-1 space-y-1">
                {exercise.pitfalls_to_avoid.map((pitfall, j) => (
                  <li key={j} className="text-xs text-muted-foreground pl-4 relative">
                    <span className="absolute left-0">•</span>
                    {pitfall}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
