const STEPS = [
  {
    n: 1,
    title: "Dépose ton CV",
    body: "Un PDF suffit. On l'analyse immédiatement.",
  },
  {
    n: 2,
    title: "Reçois ton diagnostic et tes offres",
    body: "Score ATS, mots-clés manquants, et les offres locales compatibles avec ton profil.",
  },
  {
    n: 3,
    title: "Postule mieux",
    body: "Génère un CV et une lettre adaptés à chaque offre, prépare l'entretien, suis tes candidatures.",
  },
];

export function HowItWorks() {
  return (
    <section className="border-t border-border/60 bg-muted/30">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <h2 className="font-display text-2xl font-bold text-foreground sm:text-3xl">
          Comment ça marche
        </h2>
        <div className="mt-8 grid gap-6 sm:grid-cols-3">
          {STEPS.map(({ n, title, body }) => (
            <div key={n}>
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary font-display text-sm font-bold text-primary-foreground">
                {n}
              </span>
              <h3 className="mt-3 font-display text-lg font-semibold text-foreground">
                {title}
              </h3>
              <p className="mt-1.5 text-sm text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
