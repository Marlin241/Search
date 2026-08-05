import { ScoreCircle } from "./ScoreCircle";
import type { DiagnosticReport } from "@/lib/types";

export function DiagnosticReportView({ report }: { report: DiagnosticReport }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4 rounded-xl bg-white p-4 shadow-sm">
        <ScoreCircle score={report.overall_score} size="lg" />
        <div>
          <p className="text-sm font-semibold text-slate-900">Score global</p>
          <p className="text-sm text-slate-600">Encore quelques ajustements et ce CV passera mieux les filtres.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <ScoreCircle score={report.structural_score} size="sm" />
            <p className="text-sm font-semibold text-slate-900">Structure</p>
          </div>
          {report.structural_issues.length === 0 ? (
            <p className="mt-2 text-sm text-slate-600">Aucun problème structurel détecté.</p>
          ) : (
            <ul className="mt-2 list-disc pl-5 text-sm text-slate-700">
              {report.structural_issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-xl bg-white p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <ScoreCircle score={report.semantic_score} size="sm" />
            <p className="text-sm font-semibold text-slate-900">Correspondance à l'offre</p>
          </div>
          {report.missing_keywords.length === 0 ? (
            <p className="mt-2 text-sm text-slate-600">Aucun mot-clé manquant détecté.</p>
          ) : (
            <ul className="mt-2 flex flex-wrap gap-1">
              {report.missing_keywords.map((keyword) => (
                <li key={keyword} className="rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700">
                  {keyword}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {report.recommendations.length > 0 && (
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <p className="text-sm font-semibold text-slate-900">Recommandations</p>
          <ul className="mt-2 list-disc pl-5 text-sm text-slate-700">
            {report.recommendations.map((recommendation) => (
              <li key={recommendation}>{recommendation}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
