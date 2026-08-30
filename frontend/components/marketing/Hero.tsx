import Link from "next/link";
import { TAGLINE } from "@/lib/brand";
import { UiMockup } from "./UiMockup";

export function Hero() {
  return (
    <section className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:items-center lg:py-24">
      <div>
        <h1 className="font-display text-4xl font-bold leading-tight text-foreground sm:text-5xl">
          {TAGLINE}
        </h1>
        <p className="mt-5 text-base text-muted-foreground sm:text-lg">
          Analyse ATS de ton CV, offres locales scorées pour ton profil, CV et
          lettres générés par IA, préparation d&apos;entretien : tout au même
          endroit.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <a
            href="#acces"
            className="rounded-xl bg-primary px-6 py-3 text-center text-sm font-semibold text-primary-foreground shadow-soft hover:bg-primary-600"
          >
            Demander un accès
          </a>
          <Link
            href="/login"
            className="rounded-xl border border-border px-6 py-3 text-center text-sm font-semibold text-foreground hover:bg-muted/60"
          >
            J&apos;ai un code — me connecter
          </Link>
        </div>
      </div>
      <div className="lg:pl-8">
        <UiMockup />
      </div>
    </section>
  );
}
