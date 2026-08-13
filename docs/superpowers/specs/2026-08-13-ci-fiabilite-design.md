# CI et fiabilité (lint, types, sécurité, tests) — Design

## Contexte

Le projet compte 314 tests backend (pytest, tous verts) et une suite de
tests frontend (vitest), mais rien ne les exécute automatiquement : ils ne
tournent que si quelqu'un pense à les lancer manuellement. Il n'existe pas
de configuration de lint (ni `ruff` côté backend, ni `eslint` côté
frontend), pas de vérification de types automatisée (`mypy`), pas d'audit
de sécurité (`bandit`, `pip-audit`), et pas de dépôt GitHub Actions
(`.github/workflows/`) alors que le remote `origin` existe déjà
(`git@github.com:Marlin241/Search.git`).

Ce chantier fait suite à une session de refonte UI (restylage complet du
frontend) : avant d'ajouter de nouvelles fonctionnalités (recherche
proactive, suivi de candidatures enrichi — voir « Prochaines étapes »), on
sécurise le terrain pour qu'une régression future soit détectée
automatiquement plutôt qu'en usage.

## Objectif

Mettre en place :
1. Une CI GitHub Actions qui exécute automatiquement tests, lint, types et
   audits de sécurité sur chaque push et chaque pull request vers `main`.
2. Des hooks `pre-commit` (backend) pour un feedback identique en local,
   avant même de pousser.

**Hors scope pour cette itération** (explicitement exclu) :
- L'annotation rétroactive de *tous* les fichiers backend actuellement sans
  types comme politique générale (`mypy` tourne en mode permissif — voir
  plus bas — précisément pour ne pas en faire un prérequis de ce chantier).
  Ceci n'exclut pas la correction des erreurs mypy concrètes découvertes en
  activant l'outil — voir addendum ci-dessous.
- Le déclenchement automatique du passage bandit/pip-audit en mode
  bloquant : cette bascule est un commit de suivi manuel, décidé après
  revue du premier rapport (voir « Composants » et « Prochaines étapes »).
- Le déploiement (CD) : ce chantier couvre uniquement l'intégration
  continue (vérifications), pas le déploiement automatique.

**Addendum (découverte pendant la préparation du plan d'implémentation) :**
En testant `ruff`/`mypy` contre le code existant avant d'écrire le plan,
deux hypothèses de cette spec se sont révélées fausses en pratique, et ont
été retranchées avec l'utilisateur :
- Le rule set par défaut de `ruff` flague les 9 `datetime.utcnow()`
  mentionnés plus haut comme initialement hors scope (règle `DTZ003`) — les
  laisser en l'état aurait empêché `ruff check` (bloquant) de jamais passer
  au vert. Décision : les corriger maintenant (remplacement mécanique par
  un helper `datetime.now(UTC).replace(tzinfo=None)`, comportement
  identique) plutôt que d'exclure la règle. Cette correction n'est donc
  **plus** hors scope, contrairement à la version initiale de cette section.
- L'hypothèse « le mode permissif de mypy suffit à passer immédiatement »
  était fausse : mypy remontait 38 erreurs réelles (dont ~29 après un
  premier correctif d'1 ligne dans `main.py`) même en mode permissif,
  touchant du code métier (`ats_adapters`, `job_search`, `routers`).
  Décision : les corriger maintenant plutôt que de rendre `mypy` non
  bloquant au démarrage — voir le plan d'implémentation
  (`docs/superpowers/plans/2026-08-13-ci-fiabilite.md`) pour le détail
  fichier par fichier de chaque correctif.

## Composants

### 1. Workflow GitHub Actions (`.github/workflows/ci.yml`, nouveau)

Un seul fichier, deux jobs indépendants, déclenchés sur `push` (toutes
branches) et `pull_request` vers `main` :

- **`backend`** (dans `backend/`) :
  1. Installation des dépendances (`requirements.txt` +
     `requirements-dev.txt`, complété avec `ruff`, `mypy`, `bandit`,
     `pip-audit`).
  2. `ruff check .` et `ruff format --check .` — bloquant.
  3. `mypy app` — bloquant, en mode permissif (voir composant 2).
  4. `bandit -r app -c pyproject.toml` — **non bloquant** au démarrage
     (`continue-on-error: true`), le job affiche le rapport dans les logs
     sans faire échouer la CI.
  5. `pip-audit -r requirements.txt` — **non bloquant** au démarrage, même
     traitement.
  6. `pytest` — bloquant (314 tests existants).

- **`frontend`** (dans `frontend/`) :
  1. Installation des dépendances (`npm ci`).
  2. `eslint .` — bloquant (nouvelle config, voir composant 3).
  3. `tsc --noEmit` — bloquant.
  4. `npm test` (`vitest run`) — bloquant.

Les deux jobs tournent en parallèle (aucune dépendance entre eux).

### 2. Configuration Python (`backend/pyproject.toml`, nouveau)

Le backend n'a actuellement aucun `pyproject.toml`. Il est créé avec :

- **`[tool.ruff]`** : règles par défaut de ruff (`E`, `F`, `I`...), cible
  Python 3.13 (version du `venv` existant), exclusion de `venv/`,
  `.pytest_cache/`.
- **`[tool.mypy]`** : `ignore_missing_imports = true`, pas de `--strict`,
  pas de `disallow_untyped_defs`. Comportement par défaut de mypy : les
  fonctions déjà annotées (`-> Type`) sont vérifiées, les fonctions sans
  annotation sont ignorées. Conséquence : les ~40 fichiers déjà typés
  aujourd'hui sont couverts immédiatement, sans bloquer sur le reste ; au
  fur et à mesure qu'un fichier existant gagne des annotations, mypy
  commence à le vérifier automatiquement — aucune bascule de config
  n'est nécessaire pour ce renforcement progressif.
- **`[tool.bandit]`** : exclusion de `tests/` et `venv/`.

### 3. Configuration frontend (`frontend/.eslintrc.json`, nouveau)

- Base `next/core-web-vitals` + preset TypeScript (`@typescript-eslint`),
  cohérent avec le projet Next.js 14 existant.
- Script `lint` ajouté à `frontend/package.json`
  (`"lint": "eslint . --max-warnings=0"`).
- Aucune règle personnalisée au démarrage — le préréglage `next` suffit
  pour attraper les erreurs courantes (imports inutilisés, hooks mal
  utilisés, etc.). Des règles additionnelles pourront être ajoutées plus
  tard si des problèmes récurrents apparaissent en pratique.

### 4. Hooks pre-commit (`.pre-commit-config.yaml`, nouveau, racine du dépôt)

Backend uniquement (comme convenu — le frontend n'a pas d'équivalent
pre-commit dans ce chantier, ses vérifications restent réservées à la CI) :

- `ruff` (lint + format, avec `--fix` pour le format uniquement).
- `mypy` (même configuration permissive qu'en CI).
- `bandit`.
- `pip-audit`.

`ruff` et `mypy` bloquent le commit dès l'installation du hook
(`pre-commit install`). `bandit` et `pip-audit` suivent la même
temporisation « avertir d'abord, bloquer ensuite » qu'en CI (voir
composant 1) et démarrent donc en mode non bloquant
(`verbose: true`, sortie affichée mais échec du hook ignoré) : contrairement
à `ruff`, ces deux outils scannent l'ensemble du fichier/de l'arbre
concerné à chaque exécution (pas seulement les lignes modifiées), donc les
laisser bloquants dès le départ bloquerait aussi des commits sans rapport
avec les problèmes détectés, tant que le rapport initial n'a pas été
traité. Les deux passent en mode bloquant en même temps qu'en CI, via le
même commit de suivi.

### 5. `requirements-dev.txt` (modifié)

Ajout de `ruff`, `mypy`, `bandit`, `pip-audit`, `pre-commit` aux
dépendances de développement existantes.

## Gestion des erreurs et cas limites

- **`pip-audit` en CI sans accès réseau ou avec un service tiers
  indisponible** : le job échoue sur une erreur d'outil plutôt que sur une
  vulnérabilité détectée. Comme le job est déjà non bloquant au démarrage
  (`continue-on-error: true`), cette distinction n'a pas d'impact visible
  pour l'instant ; à réévaluer si le mode bloquant est activé (prochaine
  étape).
- **Bascule bandit/pip-audit en mode bloquant** : geste manuel (retrait de
  `continue-on-error: true` dans `ci.yml`), effectué après revue du
  premier rapport généré par ce chantier. Pas de date ni de condition
  automatique déclenchant cette bascule — décision humaine.

## Validation

Avant de considérer ce chantier terminé :
1. Pousser une branche avec l'ensemble des fichiers ci-dessus et vérifier
   dans l'onglet Actions de GitHub que les deux jobs (`backend`,
   `frontend`) se déclenchent et passent au vert, avec bandit/pip-audit
   visibles en non-bloquant dans les logs du job `backend`.
2. Vérifier en local qu'un commit avec une violation ruff volontaire
   (ex: import inutilisé) est bloqué par le hook pre-commit avant d'avoir
   pu committer.
3. Consulter le rapport bandit/pip-audit de cette première exécution pour
   décider des correctifs ou acceptations nécessaires avant la bascule en
   mode bloquant (voir « Prochaines étapes »).

## Prochaines étapes (hors scope de cette spec)

- Bascule de bandit/pip-audit en mode bloquant une fois le premier rapport
  traité.
- Correction des warnings de dépréciation (`datetime.utcnow()`).
- Annotation progressive des fichiers backend non typés, au fil des
  modifications futures (pas de chantier dédié planifié).
- Chantiers suivants déjà identifiés : recherche proactive + notifications,
  puis suivi de candidatures enrichi.
