# Automatisation de candidature — Design

## Contexte

Ce document couvre le **sous-projet 2 : automatisation de candidature**, tel
qu'annoncé dans la vision globale de
`docs/superpowers/specs/2026-08-04-diagnostic-ats-design.md`. Les sous-projets
1 (diagnostic ATS) et 3 (personnalisation CV/lettre) sont terminés et
déployés : un utilisateur peut uploader son CV, fournir une offre, obtenir un
diagnostic, puis générer un CV optimisé et une lettre de motivation en PDF
pour cette offre.

Ce sous-projet s'appuie directement sur ces deux briques existantes plutôt que
de les dupliquer : une fois une offre trouvée, le diagnostic et la génération
CV/lettre sont réutilisés tels quels.

## Objectif de ce sous-projet

Permettre à un utilisateur de :
1. Définir des critères de recherche (mots-clés, localisation, type de
   contrat, télétravail, entreprises à suivre, mots-clés à exclure) et lancer
   une recherche à la demande sur plusieurs sources
2. Sélectionner les offres qui l'intéressent parmi les résultats
3. Obtenir automatiquement, pour chaque offre sélectionnée, un diagnostic
   puis un CV et une lettre de motivation personnalisés (réutilisation directe
   des sous-projets 1 et 3)
4. Relire le résultat (diagnostic, documents générés, et pour les offres
   éligibles, un aperçu du formulaire de candidature pré-rempli)
5. Confirmer la candidature : soumission automatique si l'offre est hébergée
   sur un ATS supporté (Greenhouse ou Lever), sinon préparation complète du
   dossier avec soumission manuelle par l'utilisateur

**Sources de recherche V1** : France Travail (API officielle, marché
français), Adzuna (agrégateur international avec API officielle), Greenhouse
et Lever job board APIs (recherche par entreprises suivies par l'utilisateur).
Pas de scraping de recherche sur LinkedIn/Indeed.

**Soumission automatique V1** : uniquement sur les offres hébergées sur
Greenhouse ou Lever, via des adaptateurs HTTP directs (pas de navigateur
headless). Toute autre plateforme (LinkedIn, Indeed, sites custom d'entreprise)
passe en mode assisté : dossier prêt (CV/lettre PDF + lien vers l'offre), mais
soumission manuelle par l'utilisateur — même posture que le scraper
`offer_ingestion` existant, qui ne récupère que des offres dont l'utilisateur
fournit lui-même l'URL.

**Hors scope pour cette V1** (explicitement exclu, réservé à des itérations
futures) :
- Recherche récurrente en arrière-plan / notifications de nouvelles offres
  (recherche à la demande uniquement, traitement synchrone comme les
  sous-projets 1 et 3)
- Tout login ou session automatisée sur une plateforme tierce (aucun
  identifiant de compte utilisateur tiers stocké ou utilisé)
- Navigateur headless (Playwright/Selenium) — approche gardée en réserve si
  les adaptateurs HTTP directs s'avèrent trop fragiles à l'usage
- ATS de soumission automatique au-delà de Greenhouse et Lever (l'architecture
  en adaptateurs est pensée pour en ajouter facilement par la suite)
- Suivi de statut de candidature après soumission (pas de tracking "vu par le
  recruteur", relances, etc.)
- Recherche de mots-clés à travers toutes les entreprises utilisant
  Greenhouse/Lever dans le monde (uniquement parmi les entreprises que
  l'utilisateur choisit de suivre)

## Architecture globale

```
┌─────────────────────┐   HTTP   ┌───────────────────────────────────────────┐
│ Frontend (Next.js)     │◄────────►│ Backend (FastAPI)                          │
│ - Page /candidatures :  │         │  app/job_search/     → France Travail,      │
│   critères + sélection   │         │                        Adzuna, Greenhouse/  │
│ - Revue par offre :      │         │                        Lever (lecture)      │
│   diagnostic + CV/lettre │         │  app/applications/   → orchestration,       │
│   + confirmer candidature│         │                        modèle Application,  │
│ - Page /profil            │         │                        dédoublonnage        │
└─────────────────────┘         │  app/ats_adapters/    → GreenhouseAdapter,   │
                                    │                        LeverAdapter (écriture)│
                                    │  app/offer_ingestion  → existant, réutilisé  │
                                    │                        (mode assisté)        │
                                    │  app/rules_engine,      → existants           │
                                    │  llm_analyzer,            (sous-projet 1)     │
                                    │  aggregator                                    │
                                    │  app/personalization  → existant (sous-projet 3)│
                                    └──┬──────────┬──────────┬───────────────────┘
                                       │          │          │
                       ┌───────────────▼──┐  ┌────▼─────┐ ┌─▼──────────────────┐
                       │ France Travail /    │  │ Claude API │ │ Greenhouse / Lever  │
                       │ Adzuna / GH+Lever    │  │ (existant) │ │ (soumission HTTP)    │
                       │ job board APIs        │  └──────────┘ └────────────────────┘
                       └──────────────────────┘
                                       │
                              ┌────────▼────────┐   ┌──────────┐
                              │ PostgreSQL         │   │ MinIO      │
                              │ (Application,        │   │ (existant, │
                              │  CandidateProfile)    │   │  PDFs)      │
                              └───────────────────┘   └──────────┘
```

Nouveaux modules backend, dans la continuité de la structure existante (un
dossier par responsabilité, comme `offer_ingestion`, `personalization`) :
- `app/job_search/` — clients de recherche (lecture seule)
- `app/ats_adapters/` — adaptateurs de soumission (écriture, Greenhouse/Lever)
- `app/applications/` — orchestration du pipeline complet

**Réutilisation explicite** : `rules_engine`, `llm_analyzer`, `aggregator`
(diagnostic, sous-projet 1) et `personalization` (CV/lettre, sous-projet 3)
sont appelés tels quels sur le texte de l'offre trouvée — aucune nouvelle
logique de diagnostic ou de génération de documents n'est écrite ici.

**Identifiants tiers** : les clés d'API France Travail/Adzuna sont des secrets
applicatifs (compte développeur créé par le porteur du projet, partagés pour
tous les utilisateurs — comme la clé Anthropic ou la config MinIO déjà en
place), pas des identifiants personnels d'utilisateur. Aucun identifiant de
compte tiers appartenant à un utilisateur (LinkedIn, Indeed...) n'est jamais
stocké, saisi ou utilisé.

## Modèle de données

### `CandidateProfile` (nouveau, un par utilisateur)

| Champ | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `user_id` | FK → `users`, unique, `ondelete=CASCADE` | un profil par utilisateur |
| `full_name` | str | |
| `phone` | str | |
| `address` | str, nullable | |
| `linkedin_url` | str, nullable | |
| `portfolio_url` | str, nullable | |
| `work_authorization` | str | ex: "Autorisé à travailler en France/UE" |
| `salary_expectation` | str, nullable | libre (ex: "45-55k€") |
| `cv_text` | str, nullable | texte extrait du CV de référence — permet de générer un diagnostic pour chaque offre sélectionnée sans réuploader le fichier à chaque fois ; mis à jour via un upload dédié sur la page `/profil` (même parser `cv_parser` que le sous-projet 1) |
| `cv_filename` | str, nullable | nom du fichier d'origine, pour affichage |
| `cv_has_tables` / `cv_has_multi_column` / `cv_has_images` | bool, nullable | métadonnées structurelles issues de `CVParseResult` (`cv_parser`), calculées une seule fois à l'upload et réutilisées pour chaque diagnostic — impossibles à recalculer plus tard puisque le fichier brut n'est jamais conservé |
| `cv_detected_sections` | JSON (liste de str), nullable | idem, issu de `CVParseResult.detected_sections` |
| `created_at` / `updated_at` | datetime | |

Cohérent avec l'existant : le texte extrait d'un CV est déjà persisté en base par
le sous-projet 1 (`Diagnostic.cv_text`) — le stocker une fois de plus au niveau
du profil ne change pas la posture de confidentialité déjà établie (jamais le
fichier brut, seulement le texte extrait et ses métadonnées structurelles).

### `Application` (nouveau — pivot du sous-projet)

| Champ | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `user_id` | FK → `users` | |
| `diagnostic_id` | FK → `diagnostics`, `ondelete=CASCADE` | créé en même temps que le diagnostic — pas d'état "sélectionné mais pas encore diagnostiqué" en base, cocher des offres dans les résultats de recherche est un état purement frontend et éphémère |
| `offer_url` | str | clé de dédoublonnage |
| `source` | str | `france_travail` / `adzuna` / `greenhouse` / `lever` / `manual` |
| `company_name`, `job_title` | str | dénormalisés, pour l'affichage dans l'historique sans re-fetch |
| `ats_type` | str, nullable | `greenhouse` / `lever` / `None` → détermine l'éligibilité à l'auto-submit |
| `status` | str | `en_cours` / `soumise_auto` / `a_soumettre_manuellement` / `soumise_manuelle_confirmee` / `echec_soumission` |
| `error_message` | str, nullable | renseigné si `echec_soumission` |
| `submitted_at` | datetime, nullable | |
| `created_at` / `updated_at` | datetime | |

Contrainte unique `(user_id, offer_url)` : empêche une double candidature à la
même offre, quelle que soit la source.

Transition `a_soumettre_manuellement` → `soumise_manuelle_confirmee` : bouton
"Marquer comme envoyée" côté frontend en mode assisté, pour le suivi dans
l'historique uniquement — aucune vérification technique que l'envoi a
réellement eu lieu (impossible à vérifier de l'extérieur).

### Pas de nouveaux modèles pour :
- **Les résultats de recherche bruts** : transitoires, renvoyés au frontend et
  affichés le temps de la session, jamais persistés tant qu'une offre n'est
  pas sélectionnée pour un diagnostic (évite de stocker en base des centaines
  d'offres jamais consultées)
- **Les critères de recherche** : saisis à chaque recherche côté frontend, non
  sauvegardés en V1 (cohérent avec le choix "à la demande", pas de recherche
  récurrente)

## Composants

### 1. `app/job_search/` — clients de recherche

Un client par source (`france_travail.py`, `adzuna.py`, `greenhouse.py`,
`lever.py`), chacun :
- traduit les critères utilisateur vers les paramètres propres à son API
- normalise la réponse en `JobListing` (titre, entreprise, lieu, extrait, URL,
  source, `ats_type` détecté si l'offre vient de Greenhouse/Lever)

Pour Greenhouse/Lever : recherche par entreprises suivies par l'utilisateur
(ces APIs ne permettent pas une recherche globale par mots-clés à travers
toutes les entreprises).

Erreur/timeout sur une source → elle est omise des résultats (indicateur
"source indisponible" côté frontend), les autres sources répondent
normalement — pas d'échec global de la recherche.

### 2. Sélection (frontend uniquement)

L'utilisateur coche des offres dans la liste de résultats — état local
frontend, rien en base tant que le diagnostic n'est pas lancé.

### 3. `app/applications/` — orchestration

Pré-requis : `CandidateProfile.cv_text` doit être renseigné (CV de référence
uploadé sur `/profil`) — sinon 422 propre invitant l'utilisateur à compléter
son profil avant de lancer une recherche.

Pour chaque offre cochée, au clic sur "Lancer le diagnostic" :
1. Récupération du texte complet de l'offre (via `offer_ingestion` existant
   si besoin d'aller chercher le HTML, ou directement l'extrait de l'API
   source si suffisant)
2. Vérification du dédoublonnage (`offer_url` déjà présente pour cet
   utilisateur) → rejet propre avant tout appel LLM si c'est le cas
3. Appel du pipeline diagnostic existant (`rules_engine` + `llm_analyzer` +
   `aggregator`) sur `CandidateProfile.cv_text` et ses métadonnées
   structurelles déjà stockées (pas de ré-upload, pas de re-parsing) →
   `Diagnostic` créé
4. `Application` créée dans le même mouvement, liée au `Diagnostic`, statut
   `en_cours`

### 4. Génération CV/lettre

Endpoints identiques au sous-projet 3, réutilisés tels quels sur le
`diagnostic_id` de l'`Application`.

### 5. Revue avant soumission

Le frontend affiche : le diagnostic, le CV/lettre générés, et — si
`ats_type` est renseigné — un aperçu du formulaire de candidature pré-rempli
(champs standards depuis `CandidateProfile`, champs custom répondus par un
appel LLM à partir de l'offre et du profil), modifiable avant envoi. Cette
étape de revue est le filet de sécurité principal contre les erreurs de
remplissage automatique.

### 6. `app/ats_adapters/` — soumission (Greenhouse/Lever uniquement)

- `discover_form(offer_url)` : récupère la page de candidature, en extrait les
  champs (standards + custom) et les tokens nécessaires (CSRF/session) —
  même famille de technique que `offer_ingestion/scraper.py` (`httpx` +
  `BeautifulSoup`), sans navigateur
- `answer_custom_fields(fields, candidate_profile, offer_text)` : appel Claude
  pour générer une réponse par champ custom détecté
- `submit(filled_form, cv_pdf, lettre_pdf)` : soumission HTTP (multipart,
  incluant les PDF déjà générés et stockés sur MinIO par le sous-projet 3)

Sur succès → `Application.status = soumise_auto`, `submitted_at` renseigné.
Sur échec → `Application.status = echec_soumission`, `error_message`
renseigné, **aucun retry automatique** (contrairement au pattern retry-once du
diagnostic/LLM — soumettre une candidature en double par erreur serait pire
qu'un échec visible).

Champ custom que le LLM ne peut pas remplir avec confiance (upload de fichier
autre que CV/lettre, menu déroulant à choix fermé...) → laissé vide et marqué
"à compléter" dans l'aperçu de revue plutôt que rempli au hasard.

### 7. Mode assisté (LinkedIn/Indeed/custom/offres sans `ats_type`)

Pas de formulaire pré-rempli à distance : le frontend affiche un lien vers
l'offre et les PDF déjà téléchargeables (comme le sous-projet 3), avec un
bouton "Marquer comme envoyée".

## Gestion des erreurs et cas limites

**Recherche**
- Erreur/timeout sur une source → omise des résultats, pas d'échec global
- Rate-limit dédié (compteur horaire séparé, même mécanisme que
  `app/rate_limit/`) sur le nombre de recherches — protège le quota gratuit
  d'Adzuna/France Travail, indépendamment du coût LLM

**Profil candidat incomplet**
- Génération de diagnostic/CV/lettre reste possible sans profil complet
- L'auto-submit sur une offre Greenhouse/Lever est bloqué tant que les champs
  obligatoires du profil ne sont pas remplis — message clair renvoyant vers
  la page profil, plutôt que soumettre un formulaire à moitié vide

**Formulaire ATS qui a changé de structure**
- Détecté à l'étape `discover_form` ou `submit` → `echec_soumission`, aucun
  retry automatique
- Test d'intégration par adaptateur, exécuté périodiquement (pas seulement en
  CI sur commit), qui vérifie sur une vraie offre de test que le format
  attendu est toujours valide — alerte précoce en cas de changement côté
  Greenhouse/Lever

**Dédoublonnage**
- Contrainte unique `(user_id, offer_url)`, rejet propre avant tout appel LLM
  si l'offre a déjà une `Application`

**RGPD**
- `CandidateProfile` supprimé en cascade avec le compte utilisateur
  (`ondelete=CASCADE` sur `user_id`, même convention que `Diagnostic`)
- `Application` supprimée en cascade avec son `Diagnostic` — donc déjà
  couverte par le `DELETE /diagnostics` existant du sous-projet 1, aucune
  nouvelle route de purge à écrire

## Aspects légaux et ToS

- **Recherche** : uniquement via APIs officielles (France Travail, Adzuna,
  Greenhouse/Lever job board) → aucun scraping de recherche, aucun risque ToS
  sur cette partie
- **Soumission automatique** : uniquement sur Greenhouse/Lever, via leur
  formulaire public de candidature — usage prévu de la page, pas de
  contournement d'anti-bot ni de compte à usurper
- **LinkedIn/Indeed/sites custom** : jamais d'automatisation (ni recherche, ni
  soumission) — mode assisté uniquement, même posture que le scraper
  existant du sous-projet 1 (l'utilisateur fournit une URL qu'il a trouvée
  lui-même)
- **Aucun identifiant de compte tiers utilisateur** stocké nulle part — les
  seules clés API en jeu sont des secrets applicatifs (comme pour Claude ou
  MinIO)

## Frontend

Nouvelle page `/candidatures` :
- Formulaire de critères (mots-clés, localisation, type de contrat,
  télétravail, entreprises à suivre pour Greenhouse/Lever, mots-clés à
  exclure) → bouton "Rechercher"
- Liste de résultats avec cases à cocher → bouton "Lancer le diagnostic pour
  la sélection"
- Une carte par offre sélectionnée, réutilisant `DiagnosticReportView` et
  `PersonalizedDocumentCard` (sous-projets 1 et 3) pour afficher diagnostic et
  CV/lettre générés
- Sur chaque carte : bouton "Confirmer la candidature" — déclenche la
  soumission automatique (Greenhouse/Lever) ou affiche le mode assisté (lien
  + PDF + "Marquer comme envoyée")

Nouvelle page `/profil` : formulaire `CandidateProfile` + upload du CV de
référence (réutilise `cv_parser` existant), avec indicateur clair des champs
requis pour débloquer l'auto-submit.

`/historique` (existante) étendue pour lister aussi les `Application`
(entreprise, poste, statut, date).

Extensions `lib/api.ts` / `lib/types.ts` : `searchJobs`, `createApplication`,
`submitApplication`, `markApplicationSentManually`, `getCandidateProfile`,
`updateCandidateProfile` ; types `JobListing`, `Application`,
`CandidateProfile`.

## Tests

- **`job_search/`** : tests unitaires par client, réponses HTTP mockées
  (succès/erreur/vide), sans réseau réel — même approche que `scraper.py`
- **`ats_adapters/`** : tests d'intégration sur formulaire Greenhouse/Lever
  mocké (HTML de test capturé), couvrant découverte des champs, remplissage,
  succès et échec de soumission
- **Réponse LLM aux champs custom** : mockée en tests d'intégration
  (parsing/validation testés, pas la qualité rédactionnelle — même posture
  que `semantic_analyzer`/`personalization`)
- **`applications/`** : tests d'intégration avec base de données de test —
  dédoublonnage, transitions de statut, cascade RGPD
- **Qualité des réponses générées** (champs custom) : évaluation manuelle
  périodique, comme pour le diagnostic et la personnalisation — pas de test
  automatisé sur la qualité rédactionnelle elle-même
- **Frontend** : tests légers de composants, même convention que l'existant
- **Test manuel obligatoire avant mise en production** : au moins une vraie
  candidature de bout en bout sur une offre Greenhouse et une offre Lever
  réelles (basse enjeu), pour valider que l'adaptateur fonctionne contre le
  vrai service et pas seulement contre des mocks

## Prochaines étapes (hors scope de cette spec)

- Recherche récurrente en arrière-plan avec notifications (nécessiterait un
  scheduler/job asynchrone, absent du projet actuel)
- Adaptateurs de soumission pour d'autres ATS (SmartRecruiters, Workday...)
- Navigateur headless (Playwright) si les adaptateurs HTTP directs s'avèrent
  trop fragiles à maintenir
- Suivi de statut post-soumission (relances, notifications de réponse)
