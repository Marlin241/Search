import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Politique de confidentialité — Search",
};

export default function ConfidentialitePage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-12 text-sm leading-relaxed text-foreground">
      <h1 className="mb-2 text-2xl font-display font-bold">
        Politique de confidentialité
      </h1>
      <p className="mb-8 text-xs text-muted-foreground">Version 2026-09</p>

      <Section title="1. Responsable du traitement">
        L&apos;équipe Yokkute Labs. Contact :{" "}
        <a
          className="text-primary-600 hover:underline"
          href="mailto:yokkutelabs@gmail.com"
        >
          yokkutelabs@gmail.com
        </a>
        .
      </Section>

      <Section title="2. Données collectées">
        Adresse email ; mot de passe (stocké haché, jamais en clair) ; CV et
        documents que tu téléverses ; profil candidat (nom, téléphone,
        préférences de recherche) ; historique de recherche d&apos;offres ;
        candidatures suivies ; documents générés (CV, lettres, dossiers de
        préparation) ; journaux d&apos;utilisation des fonctionnalités
        d&apos;IA (nombre d&apos;appels, volumes de texte).
      </Section>

      <Section title="3. Finalités et base légale">
        Ces données servent uniquement à fournir le service. La base légale du
        traitement est <strong>ton consentement</strong>, recueilli lors de
        l&apos;inscription (version 2026-09).
      </Section>

      <Section title="4. Sous-traitants et destinataires">
        <ul className="ml-4 list-disc space-y-1">
          <li>
            <strong>Anthropic</strong> — traitement des CV, offres et textes
            par le modèle d&apos;IA (hébergé à l&apos;étranger).
          </li>
          <li>
            <strong>Resend</strong> — envoi des emails transactionnels
            (réinitialisation de mot de passe, alertes d&apos;offres).
          </li>
          <li>Notre hébergeur cloud, basé en Europe.</li>
        </ul>
        Aucune donnée n&apos;est vendue ni utilisée à des fins publicitaires.
      </Section>

      <Section title="5. Durée de conservation">
        Tes données sont conservées tant que ton compte est actif, puis
        supprimées après 6 mois d&apos;inactivité. La suppression est immédiate
        sur demande, via le bouton « Supprimer mon compte » de ton profil.
      </Section>

      <Section title="6. Tes droits">
        Tu disposes des droits d&apos;accès, de rectification,
        d&apos;effacement et de portabilité (bouton « Exporter mes données »),
        ainsi que du droit de retirer ton consentement (équivalent à la
        suppression du compte). Pour les exercer :{" "}
        <a
          className="text-primary-600 hover:underline"
          href="mailto:yokkutelabs@gmail.com"
        >
          yokkutelabs@gmail.com
        </a>
        .
      </Section>

      <Section title="7. Réclamation">
        Tu peux introduire une réclamation auprès de la Commission de
        protection des données personnelles du Sénégal (cdp.sn).
      </Section>

      <Section title="8. Cookies">
        Le site utilise un unique cookie de session, strictement nécessaire au
        fonctionnement du service (connexion). Aucun cookie publicitaire ni de
        mesure d&apos;audience tierce.
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
      <div>{children}</div>
    </section>
  );
}
