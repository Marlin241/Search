import { ScoreCircle } from "./ScoreCircle";
import { Card } from "./ui/Card";
import { Badge } from "./ui/Badge";
import type { DiagnosticReport } from "@/lib/types";

export function DiagnosticReportView({ report }: { report: DiagnosticReport }) {
  return (
    <div className="flex flex-col gap-4">
      <Card className="flex items-center gap-4 p-4">
        <ScoreCircle score={report.overall_score} size="lg" />
        <div>
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">Score global</p>
          <p className="text-sm text-slate-600 dark:text-slate-400">
            Encore quelques ajustements et ce CV passera mieux les filtres.
          </p>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <ScoreCircle score={report.structural_score} size="sm" />
            <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">Structure</p>
          </div>
          {report.structural_issues.length === 0 ? (
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">Aucun problème structurel détecté.</p>
          ) : (
            <ul className="mt-2 list-disc pl-5 text-sm text-slate-700 dark:text-slate-300">
              {report.structural_issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <ScoreCircle score={report.semantic_score} size="sm" />
            <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">Correspondance à l'offre</p>
          </div>
          {report.missing_keywords.length === 0 ? (
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">Aucun mot-clé manquant détecté.</p>
          ) : (
            <ul className="mt-2 flex flex-wrap gap-1">
              {report.missing_keywords.map((keyword) => (
                <li key={keyword}>
                  <Badge variant="amber">{keyword}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {report.recommendations.length > 0 && (
        <Card className="p-4">
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">Recommandations</p>
          <ul className="mt-2 list-disc pl-5 text-sm text-slate-700 dark:text-slate-300">
            {report.recommendations.map((recommendation) => (
              <li key={recommendation}>{recommendation}</li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
