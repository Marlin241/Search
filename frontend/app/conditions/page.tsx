import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Conditions d'utilisation — Search",
};

export default function ConditionsPage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-12 text-sm leading-relaxed text-foreground">
      <h1 className="mb-2 text-2xl font-display font-bold">
        Conditions d&apos;utilisation
      </h1>
      <p className="mb-8 text-xs text-muted-foreground">Version 2026-09</p>

      <Section title="1. Éditeur">
        Le service « Search » est édité par l&apos;équipe Yokkute Labs.
        Contact :{" "}
        <a
          className="text-primary-600 hover:underline"
          href="mailto:yokkutelabs@gmail.com"
        >
          yokkutelabs@gmail.com
        </a>
        .
      </Section>

      <Section title="2. Objet">
        Search est un outil <strong>en version beta</strong> d&apos;aide à la
        recherche d&apos;emploi : agrégation d&apos;offres, diagnostic de
        compatibilité avec les systèmes ATS, génération de CV et de lettres de
        motivation, préparation d&apos;entretien.
      </Section>

      <Section title="3. Accès">
        L&apos;accès se fait sur invitation et est gratuit pendant la phase
        beta. L&apos;éditeur peut suspendre l&apos;accès d&apos;un compte ou
        interrompre le service à tout moment pendant cette phase.
      </Section>

      <Section title="4. Compte">
        Un compte correspond à une personne. Tu es responsable de la
        confidentialité de ton mot de passe et des actions effectuées depuis
        ton compte.
      </Section>

      <Section title="5. Usage acceptable">
        Il est interdit d&apos;automatiser abusivement l&apos;utilisation du
        service, de tenter d&apos;en contourner les limites, ou d&apos;y
        soumettre des contenus illégaux.
      </Section>

      <Section title="6. Contenu généré par IA">
        Les CV, lettres et analyses sont produits par un modèle
        d&apos;intelligence artificielle (Anthropic). Ils peuvent contenir des
        erreurs ou des approximations : tu dois les relire et les corriger
        avant tout envoi à un employeur. L&apos;éditeur ne garantit aucun
        résultat (obtention d&apos;un entretien ou d&apos;un emploi).
      </Section>

      <Section title="7. Limitation de responsabilité">
        Le service est fourni « en l&apos;état » pendant la phase beta, sans
        garantie de disponibilité ni d&apos;absence d&apos;erreur.
      </Section>

      <Section title="8. Données personnelles">
        Le traitement de tes données est décrit dans la{" "}
        <a
          className="text-primary-600 hover:underline"
          href="/confidentialite"
        >
          Politique de confidentialité
        </a>
        .
      </Section>

      <Section title="9. Offres d&apos;emploi affichées">
        Les offres affichées sur Search proviennent de sites tiers publics
        (sites d&apos;emploi, organismes, entreprises) : nous nous contentons
        de les reprendre et de les afficher. Nous ne vérifions ni
        l&apos;authenticité, ni l&apos;exactitude, ni la légalité de ces
        offres, et ne sommes partie à aucune relation entre toi et
        l&apos;employeur ou le site source. Vérifie toujours une offre avant
        d&apos;y répondre ou de transmettre des informations personnelles.
      </Section>

      <Section title="10. Évolution des conditions">
        Ces conditions peuvent être modifiées. La version en vigueur est
        indiquée en haut de cette page.
      </Section>
    </main>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-6">
      <h2 className="mb-2 text-base font-semibold">{title}</h2>
      <p>{children}</p>
    </section>
  );
}
