import { AccessRequestForm } from "./AccessRequestForm";

export function AccessSection() {
  return (
    <section id="acces" className="mx-auto max-w-lg px-4 py-20 sm:px-6">
      <div className="text-center">
        <h2 className="font-display text-2xl font-bold text-foreground sm:text-3xl">
          Rejoindre la beta
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          On ouvre l&apos;accès progressivement à un petit groupe de chercheurs
          d&apos;emploi. Laisse-nous ton email.
        </p>
      </div>
      <div className="relative mt-8">
        <AccessRequestForm />
      </div>
    </section>
  );
}
