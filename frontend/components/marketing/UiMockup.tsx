export function UiMockup() {
  return (
    <div
      aria-hidden="true"
      className="glass rounded-3xl border border-border/60 p-5 shadow-2xl"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-muted-foreground">
          Score de compatibilité
        </span>
        <span className="rounded-full bg-success px-2 py-0.5 text-xs font-bold text-white">
          92%
        </span>
      </div>
      <p className="mt-2 text-sm font-medium text-foreground">
        Développeur back-end · Sonatel (Dakar)
      </p>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div className="h-full w-[92%] rounded-full bg-gradient-to-r from-primary-600 to-accent" />
      </div>
      <div className="mt-4 space-y-2 border-t border-border/60 pt-4">
        <p className="text-xs font-semibold text-muted-foreground">
          Mots-clés manquants sur ton CV
        </p>
        <div className="flex flex-wrap gap-1.5">
          {["CI/CD", "PostgreSQL", "REST", "Docker"].map((k) => (
            <span
              key={k}
              className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary"
            >
              {k}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
