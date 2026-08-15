import { ScoreCircle } from "./ScoreCircle";
import { Card } from "./ui/Card";
import { Badge } from "./ui/Badge";
import type { DiagnosticReport } from "@/lib/types";

function scoreTone(score: number): { className: string; label: string; description: string } {
  if (score >= 80) {
    return {
      className: "bg-success-soft text-success-ink",
      label: "Prêt à envoyer",
      description:
        "Ton CV passe très bien les filtres ATS pour cette offre. Encore quelques détails et il sera irréprochable.",
    };
  }
  if (score >= 50) {
    return {
      className: "bg-pending-soft text-pending-ink",
      label: "Sur la bonne voie",
      description: "De bonnes bases. Quelques ajustements ciblés vont nettement améliorer tes chances face à l'ATS.",
    };
  }
  return {
    className: "bg-accent-soft text-accent-ink",
    label: "Point de départ",
    description:
      "C'est le point de départ, pas une note finale. On te montre exactement quoi ajuster pour progresser vite.",
  };
}

export function DiagnosticReportView({ report }: { report: DiagnosticReport }) {
  const tone = scoreTone(report.overall_score);

  return (
    <div className="flex flex-col gap-5">
      <div className={`relative overflow-hidden rounded-[32px] p-8 ${tone.className}`}>
        <div className="flex flex-wrap items-center gap-8">
          <ScoreCircle score={report.overall_score} size="lg" />
          <div className="min-w-[220px] flex-1">
            <p className="font-display text-xl font-extrabold sm:text-2xl">{tone.label}</p>
            <p className="mt-2 max-w-sm text-[14.5px] opacity-85">{tone.description}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <ScoreCircle score={report.structural_score} size="sm" />
            <p className="text-[14.5px] font-bold text-ink">Structure du CV</p>
          </div>
          {report.structural_issues.length === 0 ? (
            <p className="mt-3 text-sm text-ink-soft">Aucun problème structurel détecté.</p>
          ) : (
            <ul className="mt-3 flex flex-col gap-1.5">
              {report.structural_issues.map((issue) => (
                <li key={issue} className="flex gap-2 text-[13.5px] text-ink-soft">
                  <span>•</span>
                  {issue}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-3">
            <ScoreCircle score={report.semantic_score} size="sm" />
            <p className="text-[14.5px] font-bold text-ink">Correspondance à l&apos;offre</p>
          </div>
          {report.missing_keywords.length === 0 ? (
            <p className="mt-3 text-sm text-ink-soft">Aucun mot-clé manquant détecté.</p>
          ) : (
            <ul className="mt-3 flex flex-wrap gap-1.5">
              {report.missing_keywords.map((keyword) => (
                <li key={keyword}>
                  <Badge variant="accent">{keyword}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {report.recommendations.length > 0 && (
        <Card className="p-5">
          <p className="text-[15px] font-bold text-ink">Ce qu&apos;on te conseille</p>
          <ul className="mt-3 flex flex-col gap-2.5">
            {report.recommendations.map((recommendation, index) => (
              <li key={recommendation} className="flex gap-2.5 text-sm text-ink">
                <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-accent-soft text-[11px] font-extrabold text-accent-ink">
                  {index + 1}
                </span>
                {recommendation}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
