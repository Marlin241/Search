import { ScanSearch, MapPin, FileText, MessagesSquare } from "lucide-react";

const FEATURES = [
  {
    icon: ScanSearch,
    title: "Diagnostic ATS instantané",
    body: "Score de lisibilité de ton CV et liste des mots-clés manquants, en quelques secondes.",
  },
  {
    icon: MapPin,
    title: "Offres agrégées, scorées pour toi",
    body: "France Travail, jobboards locaux, offres remote… agrégées, avec un score de compatibilité par offre.",
  },
  {
    icon: FileText,
    title: "CV & lettre générés par IA",
    body: "Personnalisés pour l'offre visée, éditables, transparents sur ce qui a été modifié.",
  },
  {
    icon: MessagesSquare,
    title: "Préparation d'entretien IA",
    body: "Questions probables, recherche sur l'entreprise, checklist de coaching avant le jour J.",
  },
];

export function FeatureGrid() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
      <h2 className="font-display text-2xl font-bold text-foreground sm:text-3xl">
        Ce que tu peux faire
      </h2>
      <div className="mt-8 grid gap-5 sm:grid-cols-2">
        {FEATURES.map(({ icon: Icon, title, body }) => (
          <div
            key={title}
            className="rounded-2xl border border-border/60 bg-card p-6"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Icon className="h-5 w-5" />
            </span>
            <h3 className="mt-4 font-display text-lg font-semibold text-foreground">
              {title}
            </h3>
            <p className="mt-1.5 text-sm text-muted-foreground">{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
