# Diagnostic ATS — Frontend — Design

## Contexte

Ce document couvre le frontend du sous-projet **Diagnostic ATS**, dont la vision
globale et le backend sont décrits dans
[`2026-08-04-diagnostic-ats-design.md`](2026-08-04-diagnostic-ats-design.md).
Le backend FastAPI est entièrement implémenté (77 tests passants, voir
`docs/superpowers/plans/2026-08-04-diagnostic-ats-backend.md`) et expose :

- `POST /auth/register`, `POST /auth/login` (retourne un JWT), `GET /auth/me`
- `POST /diagnostics` (upload CV PDF/DOCX + texte ou URL d'offre, retourne un
  `DiagnosticReport`)
- `GET /diagnostics` (historique), `DELETE /diagnostics` (suppression RGPD de
  tout l'historique de l'utilisateur — pas de suppression individuelle)
- CORS déjà configuré pour `http://localhost:3000`

Ce document couvre uniquement le frontend Next.js/React qui consomme cette
API.

## Objectif

Permettre à un utilisateur connecté de :
1. S'inscrire / se connecter
2. Uploader son CV et fournir une offre d'emploi (texte collé ou URL)
3. Voir le rapport de diagnostic (scores + issues + mots-clés manquants +
   recommandations)
4. Consulter et purger son historique de diagnostics

**Hors scope pour cette V1** : édition/réécriture du CV, génération de lettre
de motivation, i18n de l'interface (l'UI est en français uniquement — le
support FR/EN concerne le contenu du CV/offre analysé par le backend, pas les
libellés de l'interface), tests end-to-end automatisés, dark mode.

## Prérequis backend

`DiagnosticReport` (dans `backend/app/schemas/diagnostic.py`) et le endpoint
`GET /diagnostics` (dans `backend/app/routers/diagnostics.py`) doivent être
étendus avec `id: int` et `created_at: datetime`, pour que la page Historique
puisse identifier et dater chaque diagnostic. C'est un ajout mineur (2
champs sur le modèle de sortie, déjà présents sur le modèle ORM
`Diagnostic`) — première tâche du plan d'implémentation, avant le travail
frontend proprement dit.

## Stack

- **Next.js 14+ (App Router)**, TypeScript
- **Tailwind CSS** pour le styling
- Pas de librairie de data-fetching (React Query/SWR) : seulement 4
  endpoints, pas de besoin de cache complexe — un client API maison
  (`fetch` typé) suffit
- **Vitest + React Testing Library** pour les quelques tests de composants
  (voir section Tests)

## Identité visuelle

Ton "rassurant / accompagnement" plutôt que verdict froid ou alarmiste :
bleu doux (`#3b82f6` sur fond `#f7f9fc`/blanc), cercle de progression pour
les scores, messages qui encouragent à l'action plutôt que sanctionnent.
Validé via mockup pendant le brainstorm (comparé à une variante "clinique
noir & blanc" et une variante "sombre/urgente", écartées).

## Pages / routes

| Route | Contenu |
|---|---|
| `/login` | Formulaire connexion/inscription avec bascule (un seul composant `AuthForm`, deux modes) |
| `/diagnostic` | Page d'accueil connectée : formulaire une page (upload CV + offre + bouton "Analyser") ; le rapport s'affiche sous le formulaire après soumission, sans navigation |
| `/historique` | Liste des diagnostics passés (cards résumé : score global + date), clic → accordion inline avec le rapport complet |
| `/` | Redirige vers `/diagnostic` si connecté, sinon vers `/login` |

Le formulaire de diagnostic est une page unique (pas de wizard multi-étapes)
: zone d'upload CV, onglets "Coller le texte" / "URL de l'offre" (un seul
champ actif envoyé au backend, aligné avec l'API qui n'accepte qu'une des
deux sources à la fois), bouton "Analyser mon CV".

## Auth & état

- `AuthContext` React (fournisseur global) expose `user`, `token`,
  `login()`, `logout()`. Le JWT est stocké en `localStorage`, relu au
  chargement de l'app.
- Le client API injecte automatiquement `Authorization: Bearer <token>` sur
  chaque appel authentifié.
- Un composant `RequireAuth` protège `/diagnostic` et `/historique` :
  redirige vers `/login` si aucun token valide n'est présent.
- Sur une réponse `401` de l'API (token expiré/invalide), le token local est
  effacé et l'utilisateur est redirigé vers `/login`.

## Flux de données

- **Soumission diagnostic** : `POST /diagnostics` en
  `multipart/form-data`. Pendant l'appel (quelques secondes), le bouton
  "Analyser" passe en état chargement avec un message rassurant ("Analyse
  en cours, ça prend quelques secondes...") ; le formulaire reste visible
  mais désactivé. Validation client basique avant envoi (type de fichier
  PDF/DOCX, taille ≤ 5 Mo) pour éviter un aller-retour réseau inutile — la
  validation faisant foi reste côté backend.
- **Résultat** : au retour de l'appel, le rapport s'affiche directement
  sous le formulaire via le composant partagé `<DiagnosticReportView>`.
- **Historique** : `GET /diagnostics` chargé au montage de la page
  `/historique`, déjà trié par date décroissante côté backend. Bouton
  "Supprimer tout mon historique" → `DELETE /diagnostics`, avec une
  confirmation modale avant l'appel (purge totale et irréversible, pas de
  suppression individuelle possible côté API).

## Composants principaux

- `<ScoreCircle score={n} size="lg"|"sm">` — cercle de progression bleu,
  réutilisé pour le score global (grand) et structure/sémantique (petit)
- `<CVDropzone>` — zone drag & drop + sélection fichier, validation client
  (type, taille) avant l'appel API
- `<OfferInput>` — les deux onglets "Coller le texte" / "URL"
- `<DiagnosticReportView report={...}>` — composant central du rapport
  (score global, structure + issues, correspondance + mots-clés manquants,
  recommandations), partagé entre `/diagnostic` et l'accordion de
  `/historique`
- `<AuthForm mode="login"|"register">` — formulaire email/mot de passe avec
  bascule de mode

## Gestion des erreurs

Le backend renvoie déjà des messages `detail` clairs en français (ex: "Ce
CV semble être une image scannée...", "Cet email est déjà utilisé."). Le
frontend les affiche tels quels, sans remapping de texte :

| Code | Origine | Traitement UI |
|---|---|---|
| 401 | Token absent/expiré | Redirection silencieuse vers `/login`, token local effacé |
| 409 | Email déjà utilisé (register) | Erreur inline sous le champ email |
| 422 | CV invalide, offre invalide/manquante | Bannière d'erreur au-dessus du formulaire, `detail` affiché tel quel |
| 429 | Rate limit dépassé | Bannière orange avec le `detail` du backend |
| 503 | LLM indisponible | Bannière avec `detail`, invite à réessayer dans quelques instants |
| Réseau (fetch échoue) | Backend injoignable | Bannière générique "Impossible de contacter le serveur." |

## Tests

Conformément à la spec globale (le risque principal du projet est côté
backend et qualité du diagnostic, pas côté UI) : tests légers pour cette
V1.
- Tests manuels du parcours complet avant chaque livraison : inscription →
  connexion → upload → diagnostic → historique → suppression
- Quelques tests de composants ciblés (Vitest + React Testing Library) sur
  la logique la plus sujette aux régressions silencieuses : bascule
  `AuthForm` login/register, bascule des onglets `OfferInput`, rendu
  conditionnel de `ScoreCircle`
- Pas de tests end-to-end (Playwright/Cypress) en V1

## Prochaines étapes (hors scope de cette spec)

Une fois le frontend du diagnostic livré et testé manuellement, les deux
sous-projets suivants (automatisation de candidature, personnalisation)
pourront être brainstormés séparément, comme prévu dans la spec globale.
