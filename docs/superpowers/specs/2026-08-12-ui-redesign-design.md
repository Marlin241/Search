# Refonte UI/UX de l'application — Design

## Contexte

L'application (candidature diagnostic ATS + recherche/candidature automatisée
façon Hirly) fonctionne mais n'a aucune identité visuelle : Next.js + Tailwind
vanilla, palette `slate`/`blue` par défaut, styles Tailwind dupliqués page par
page, icônes emoji. L'utilisateur veut une passe UI/UX complète inspirée de
l'app de référence Hirly (tryhirly.com) — même langage de composants (badges
pilule, cartes, boutons arrondis) — sans en être un clone visuel.

Ce document couvre uniquement l'aspect visuel/structurel : couleurs,
typographie, composants partagés, structure de navigation, dark mode. Il ne
change aucune logique métier, aucun appel API, aucun flux existant.

## Objectif

Donner à l'application une identité visuelle cohérente et professionnelle,
appliquée sur l'ensemble des pages (login, diagnostic, candidatures,
historique, profil) et de la navigation, via un petit design system partagé
plutôt que du Tailwind dupliqué par page.

**Hors scope pour cette itération** (explicitement exclu) :
- Tout changement de logique/comportement des pages (fetch, handlers, states,
  routes) — passe purement visuelle sur des composants qui fonctionnent déjà.
- Toggle dark/light manuel côté utilisateur — les tokens dark sont posés
  proprement (classe `dark:` Tailwind) mais sans interrupteur dans l'UI pour
  l'instant ; le thème actif reste déterminé par la préférence système
  (`prefers-color-scheme`) via la stratégie Tailwind choisie.
- Interaction de type swipe façon Hirly sur la page Candidatures — décision
  assumée en brainstorming : l'app est un outil web/desktop, pas une appli
  mobile, une liste de cartes sélectionnables reste plus efficace pour trier
  plusieurs offres à la fois.
- Renommage du produit (le nom affiché reste à définir séparément, hors
  périmètre visuel) — les maquettes utilisent un nom provisoire
  (« Hirly·ATS ») uniquement pour visualiser la charte, pas une décision de
  branding.
- Tests de régression visuelle automatisés — aucun outil de ce type n'est en
  place dans le projet ; la vérification reste la relecture manuelle de
  chaque page migrée, page par page, combinée aux tests vitest existants.

## Décisions validées (compagnon visuel)

Ces choix ont été comparés visuellement et validés un par un avant d'écrire
cette spec :

1. **Ampleur** : design system complet dès le départ (tokens + composants
   partagés), réappliqué sur toutes les pages plutôt qu'une page pilote isolée.
2. **Direction visuelle** : palette **« sobre & rassurant »** — pas de
   dégradé, accent ambre unique sur fond ardoise/blanc, plutôt qu'un dégradé
   violet→bleu façon clone de Hirly. Justification : c'est un outil qui
   manipule des documents de candidature (CV, lettres), la sobriété inspire
   plus confiance qu'une esthétique très « appli consumer ».
3. **Navigation** : sidebar verticale fixe à gauche plutôt qu'une barre
   horizontale — l'app a 4 sections + session, une sidebar scale mieux et
   laisse plus de largeur pour les listes/tableaux de candidatures.
4. **Interaction Candidatures** : liste de cartes sélectionnables (existant,
   restylé) plutôt qu'un swipe une-offre-à-la-fois.
5. **Typographie** : Inter, déjà en place — aucune migration de police
   nécessaire.
6. **Icônes** : migration des emojis vers `lucide-react`.
7. **Dark mode** : inclus dès cette phase (tokens définis et testés dans le
   compagnon visuel), pas seulement préparé pour plus tard.

## Design tokens

### Couleurs (Tailwind `theme.extend.colors`, valeurs `slate`/`amber`/`emerald`/`red` du palette Tailwind par défaut — pas de couleurs custom à définir)

| Rôle | Light | Dark |
|---|---|---|
| Fond de page | `slate-50` | `slate-950`-ish (`#0b0f16`, à ajouter comme `ink-950` custom) |
| Surface (cartes, sidebar) | `white` | `#131924` (custom `ink-900`) |
| Bordure | `slate-200` | `#232b3a` (custom `ink-800`) |
| Texte primaire | `slate-900` | `slate-50` |
| Texte secondaire | `slate-600` | `slate-400` |
| Accent (badges, liens actifs) | `amber-600` texte / `amber-100` fond | `amber-400` texte / fond ambre très sombre custom |
| CTA principal | fond `slate-900`, texte blanc | fond `slate-50`, texte `slate-900` (inversion) |
| Statut succès | `emerald-600`/`emerald-50` | `emerald-400`/fond sombre |
| Statut attente | `amber-600`/`amber-50` | `amber-400`/fond sombre |
| Statut échec | `red-600`/`red-50` | `red-400`/fond sombre |

Les trois teintes `ink-*` custom (fond/surface/bordure du dark mode) sont la
seule addition à `tailwind.config.ts` — tout le reste utilise la palette
Tailwind standard, pour rester simple à maintenir.

### Typographie

Inter (déjà chargée). Titres de page en `font-extrabold tracking-tight`,
corps en `font-normal`/`font-semibold` selon le contexte, comme aujourd'hui —
seule la hiérarchie des tailles est resserrée pour donner plus de poids aux
titres (`text-2xl` au lieu de `text-xl` sur les H1 de page).

### Forme

- Cartes/panneaux : `rounded-xl` à `rounded-2xl`, `border border-{border-token}`, `shadow-sm` (jamais plus lourd).
- Boutons, badges, tags, inputs de critères : `rounded-full`.
- Champs de formulaire classiques (texte libre) : `rounded-lg`.

### Icônes

`lucide-react`, taille 16–18px selon contexte, `stroke-width={2}`, couleur
héritée du texte parent (`currentColor`) pour suivre automatiquement les
tokens light/dark plutôt que d'être codée en dur icône par icône.

## Composants partagés (`components/ui/`, nouveau dossier)

Actuellement chaque page réécrit son propre Tailwind inline pour les mêmes
éléments (bouton primaire, badge de statut, carte blanche à ombre légère).
Cette refonte introduit 4 primitives réutilisées partout :

- **`Button`** — variants `primary` (fond encre), `secondary` (bordure), `danger` (rouge, pour les actions destructrices existantes) ; tailles `sm`/`md`.
- **`Card`** — conteneur `rounded-2xl border shadow-sm`, remplace les `<div className="rounded-xl bg-white p-4 shadow-sm">` dupliqués (ex. `ApplicationCard.tsx`).
- **`Badge`** — remplace les `<span className="rounded-full ...">` de statut (`STATUS_LABELS` dans `ApplicationCard.tsx`) et les tags de critères (`SearchCriteriaForm`, `JobListingsList`).
- **`Input`** / **`TextField`** — champs texte/nombre standardisés (`OfferInput`, `SearchCriteriaForm`, `AuthForm`, `CandidateProfileForm`).

Ces composants sont des wrappers de présentation uniquement (props `variant`,
`children`, pas de logique) — les composants existants gardent tout leur
state et leurs handlers, ils changent seulement le balisage qu'ils rendent.

## Structure de navigation

`components/TopNav.tsx` → renommé `components/Sidebar.tsx`. `app/layout.tsx`
passe d'un empilement vertical (`<TopNav />` puis `{children}`) à une mise en
page `flex` horizontale : sidebar fixe à gauche (largeur ~200px), contenu
scrollable à droite.

Contenu de la sidebar (repris de la nav actuelle, juste réagencé
verticalement) : logo/marque en haut, 4 liens (Diagnostic, Candidatures,
Historique, Profil) avec état actif visuel (fond encre plein, comme validé
dans le mockup), email de l'utilisateur + bouton déconnexion en bas de
sidebar. L'état « non connecté » (actuellement une barre simple avec juste le
logo) reste une variante minimale sans les liens.

## Dark mode

Stratégie Tailwind `darkMode: "media"` (suit `prefers-color-scheme`, pas de
toggle UI). Tous les composants utilisent les paires `bg-white dark:bg-ink-900`
etc. plutôt que des couleurs en dur, pour que l'ajout d'un toggle manuel plus
tard ne nécessite de retoucher que la config Tailwind (`darkMode: "class"`) et
un bouton, pas les composants.

## États (loading / vide / erreur)

- **Loading** : les boutons avec état `isSubmitting`/`isSearching` gardent
  leur texte dynamique existant, mais avec un spinner (icône `Loader2` de
  lucide, animée) au lieu du seul changement de texte.
- **Vide** : les sections qui n'affichent rien aujourd'hui quand une liste
  est vide (ex. candidatures avant recherche) reçoivent un état vide simple
  (icône + phrase courte), pour éviter l'impression de page cassée.
- **Erreur** : `ErrorBanner.tsx` est restylé avec les nouveaux tokens
  (`red-*` clair/sombre) mais garde exactement son API et son comportement
  actuels.

## Périmètre d'application

Toutes les pages existantes sont migrées vers les nouveaux tokens et
composants, sans changement de comportement : `login`, `diagnostic`,
`candidatures`, `historique`, `profil`, plus les composants partagés qui les
composent (`ApplicationCard`, `DiagnosticReportView`, `ScoreCircle`,
`JobListingsList`, `PersonalizedDocumentCard`, `PrefilledFormReview`,
`CVDropzone`, `ConfirmDialog`, `ErrorBanner`, `SearchCriteriaForm`,
`OfferInput`, `CandidateProfileForm`, `AuthForm`).

## Tests

Les tests vitest existants (`*.test.tsx`) vérifient du comportement (rendu
conditionnel, clics, appels API mockés) et non des classes CSS précises — ils
doivent rester verts sans modification après la migration visuelle de chaque
composant. Ils sont relancés après chaque page/composant migré pour confirmer
qu'aucune régression fonctionnelle n'a été introduite par le changement de
balisage.
