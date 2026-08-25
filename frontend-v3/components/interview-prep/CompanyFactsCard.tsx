import { ShieldCheck, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { CompanyFacts } from "@/lib/types";

const FACT_LABELS: { key: keyof CompanyFacts; label: string }[] = [
  { key: "founding_year", label: "Fondée en" },
  { key: "headquarters", label: "Siège" },
  { key: "sector", label: "Secteur" },
  { key: "revenue", label: "Chiffre d'affaires" },
  { key: "ceo", label: "Dirigeant" },
];

export function CompanyFactsCard({ facts }: { facts: CompanyFacts }) {
  const verified = facts.confidence === "verified_web_search";
  const populatedFacts = FACT_LABELS.filter(({ key }) => facts[key]);

  return (
    <div className="rounded-xl border border-border p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-bold text-foreground">Faits sur l&apos;entreprise</h4>
        {verified ? (
          <Badge variant="success" size="sm">
            <ShieldCheck className="w-3 h-3 mr-1" />
            Vérifié par recherche web
          </Badge>
        ) : (
          <Badge variant="warning" size="sm">
            <ShieldAlert className="w-3 h-3 mr-1" />
            Connaissance générale non vérifiée
          </Badge>
        )}
      </div>

      {populatedFacts.length > 0 ? (
        <dl className="grid grid-cols-2 gap-3 text-xs">
          {populatedFacts.map(({ key, label }) => (
            <div key={key}>
              <dt className="text-muted-foreground">{label}</dt>
              <dd className="font-semibold text-foreground">{String(facts[key])}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-xs text-muted-foreground">Aucun fait spécifique disponible.</p>
      )}

      {!verified && (
        <p className="text-xs text-warning-dark bg-warning/10 border border-warning/30 rounded-lg p-2">
          Ces informations n&apos;ont pas été confirmées par une recherche web récente — vérifiez-les
          avant l&apos;entretien.
        </p>
      )}
    </div>
  );
}
