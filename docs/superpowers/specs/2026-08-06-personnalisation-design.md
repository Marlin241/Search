# Personnalisation (CV + lettre de motivation) — Design

## Contexte

Ce document couvre le **sous-projet 3 : Personnalisation**, tel qu'annoncé
dans la section "Prochaines étapes" de
`docs/superpowers/specs/2026-08-04-diagnostic-ats-design.md`. Le sous-projet 1
(diagnostic ATS) est terminé et déployé : un utilisateur peut uploader un CV,
fournir une offre, et obtenir un diagnostic (score + mots-clés manquants +
recommandations) sauvegardé en base.

Ce sous-projet s'appuie directement sur ce diagnostic existant : à partir d'un
diagnostic déjà produit, l'utilisateur peut générer une version de CV
optimisée pour l'offre, et une lettre de motivation adaptée.

## Objectif de ce sous-projet

Permettre à un utilisateur, depuis un diagnostic qu'il vient de générer, de :
1. Générer un CV entièrement réécrit et optimisé pour l'offre analysée,
   restitué en PDF prêt à l'emploi
2. Générer une lettre de motivation adaptée à la même offre, également en PDF

Les deux actions sont indépendantes (un utilisateur peut ne vouloir que l'une
des deux) et réutilisent les données déjà stockées par le diagnostic
(`cv_text`, `offer_text`, mots-clés manquants, recommandations) — aucune
resaisie n'est nécessaire.

**Hors scope pour cette V1** (explicitement exclus, réservés à des itérations
futures) :
- Choix entre plusieurs templates de mise en page
- Export DOCX (PDF uniquement)
- Historique de versions des documents générés (une régénération remplace la
  version précédente)
- Déclenchement de la personnalisation depuis `/historique` (uniquement
  disponible juste après un diagnostic fraîchement généré, sur `/diagnostic`)
- Recherche automatique d'offres et candidature automatique (sous-projet 2)

## Architecture globale

```
┌──────────────────┐         ┌──────────────────────────┐
│  Frontend          │  HTTP   │  Backend (FastAPI)         │
│  Next.js/React      │◄──────►│                            │
│  - Page /diagnostic  │         │  - app/personalization/    │──────► Claude API
│    (boutons CV/lettre)│        │  - app/rate_limit/          │      (Sonnet 5)
└──────────────────┘         │  - app/storage/ (MinIO client)│
                               └──────┬─────────────┬───────┘
                                      │             │
                              ┌───────▼──────┐  ┌───▼──────────┐
                              │  PostgreSQL   │  │  MinIO        │
                              │  (métadonnées)│  │  (PDF stockés)│
                              └──────────────┘  └──────────────┘
```

Stack additionnelle par rapport au sous-projet 1 :
- **LLM** : API Claude, modèle **Sonnet 5** (`claude-sonnet-5`) — qualité
  rédactionnelle supérieure à Haiku, justifiée ici car le contenu généré est
  envoyé tel quel à un recruteur (contrairement au score du diagnostic)
- **Génération PDF** : `fpdf2` (déjà présent comme dépendance de dev pour les
  fixtures de test du sous-projet 1, promu en dépendance de production)
- **Stockage objet** : MinIO, auto-hébergé via Docker Compose (nouveau
  service dans `docker-compose.yml`), pour les fichiers PDF générés

## Composants

### 1. CV Rewriter (`app/personalization/analyzer.py`)

- **Entrée** : `cv_text`, `offer_text`, `missing_keywords`, `recommendations`
  (tous déjà en base, issus du `Diagnostic`)
- **Sortie** : CV réécrit, structuré par sections (résumé/accroche,
  expériences, formation, compétences...), via tool-use forcé Claude Sonnet
- **Consigne anti-hallucination dans le prompt** : interdiction explicite
  d'inventer une expérience, une compétence, une date ou un diplôme non
  présents dans le CV original — uniquement reformuler, réorganiser et mettre
  en avant l'existant avec le vocabulaire de l'offre
- Même pattern que `SemanticAnalyzer` du sous-projet 1 : 1 retry automatique
  sur échec/réponse mal formée avant erreur propre

### 2. Cover Letter Generator (`app/personalization/analyzer.py`)

- **Entrée** : mêmes données que le CV Rewriter
- **Sortie** : lettre de motivation structurée (formule d'appel, corps,
  formule de politesse), via tool-use forcé Claude Sonnet
- Même pattern de retry

### 3. Deterministic Verification (`app/personalization/verification.py`)

- **Entrée** : `cv_text` original + CV réécrit
- **Sortie** : booléen `needs_review`
- Compare les noms d'employeurs, intitulés de diplômes et dates extraits du
  CV réécrit à ceux extraits de `cv_text` — si un élément apparaît dans la
  sortie sans être présent dans l'original, `needs_review = True`
- Garde-fou léger et déterministe (pas de second appel LLM) : n'empêche pas
  la génération, signale juste à l'utilisateur qu'une relecture attentive est
  nécessaire
- S'applique uniquement au CV (pas de notion équivalente pour la lettre)

### 4. PDF Generator (`app/personalization/pdf_generator.py`)

- **Entrée** : CV réécrit structuré, ou lettre structurée
- **Sortie** : fichier PDF (bytes)
- Un seul template épuré et ATS-friendly par type de document (CV / lettre),
  pas de personnalisation de mise en page en V1

### 5. Storage (`app/storage/`)

- Client MinIO (S3-compatible, `boto3`)
- Upload/remplacement d'objet à la clé
  `users/{user_id}/diagnostics/{diagnostic_id}/{kind}.pdf`
  (`kind` = `cv` ou `lettre`)
- Suppression d'objet (pour la purge RGPD)

## Modèle de données

Nouveau modèle `PersonalizedDocument` :

| Champ | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `diagnostic_id` | FK → `Diagnostic`, `ondelete=CASCADE` | |
| `kind` | str | `"cv"` ou `"lettre"` |
| `storage_key` | str | Chemin de l'objet dans MinIO |
| `needs_review` | bool | Résultat de la vérification déterministe (toujours `False` pour `kind="lettre"`) |
| `created_at` | datetime | |
| `updated_at` | datetime | Mis à jour à chaque régénération |

Contrainte unique sur `(diagnostic_id, kind)` : un diagnostic n'a au plus
qu'un CV optimisé et qu'une lettre "courants" — régénérer met à jour la même
ligne (upsert) et écrase l'objet MinIO existant à la même clé.

## API

Deux nouveaux endpoints de génération et deux de téléchargement, tous sous
`/diagnostics/{diagnostic_id}` et protégés par `get_current_user` (le
diagnostic doit appartenir à l'utilisateur courant, sinon 404) :

- `POST /diagnostics/{id}/cv` — génère ou régénère le CV optimisé
- `POST /diagnostics/{id}/lettre` — génère ou régénère la lettre
- `GET /diagnostics/{id}/cv` — télécharge le PDF du CV actuel (404 si jamais
  généré)
- `GET /diagnostics/{id}/lettre` — télécharge le PDF de la lettre actuelle
  (404 si jamais générée)

### Flux d'une requête `POST`

1. Verrouillage + vérification du rate-limit dédié personnalisation (même
   mécanisme que `app/rate_limit/limiter.py` pour les diagnostics, mais
   compteur séparé)
2. Chargement du `Diagnostic` (vérification de propriété → 404 sinon)
3. Appel Claude Sonnet (CV Rewriter ou Cover Letter Generator selon
   l'endpoint)
4. Pour le CV uniquement : vérification déterministe → `needs_review`
5. Génération du PDF
6. Upload vers MinIO (écrase l'objet existant à la même clé s'il y en a un)
7. Upsert de la ligne `PersonalizedDocument` (commit **après** la réussite de
   l'upload MinIO — pas d'écriture DB si l'upload échoue)
8. Réponse : métadonnées (`kind`, `needs_review`, `created_at`) — le
   téléchargement se fait ensuite via l'endpoint `GET` correspondant

## Gestion des erreurs et cas limites

**Appel LLM**
- Timeout/erreur API → 1 retry automatique (comme le sous-projet 1), puis
  erreur 503 propre à l'utilisateur

**Rate-limit**
- Compteur dédié personnalisation, séparé de celui des diagnostics (ex. 10
  générations/heure, CV et lettre confondus) — 429 si dépassé

**Stockage**
- Échec d'upload MinIO → 503, aucune ligne `PersonalizedDocument` créée ou
  mise à jour (l'upload précède le commit)

**Diagnostic introuvable ou n'appartenant pas à l'utilisateur**
- 404, même comportement que les autres routes protégées par utilisateur

**RGPD**
- `DELETE /diagnostics` (purge d'historique existante) doit désormais aussi
  supprimer, pour chaque diagnostic de l'utilisateur, les objets MinIO
  associés et les lignes `PersonalizedDocument` correspondantes

**Hallucination du LLM (CV)**
- Prompt strict (interdiction d'inventer du contenu) + vérification
  déterministe légère (`needs_review`) + bandeau d'avertissement côté UI
  ("relisez avant d'envoyer") — pas de second appel LLM de vérification

## Frontend

Sur `frontend/app/diagnostic/page.tsx`, sous le rapport de diagnostic déjà
affiché (`DiagnosticReportView`), deux nouveaux boutons apparaissent une fois
`report.id` disponible :
- **"Générer CV optimisé"**
- **"Générer lettre de motivation"**

Nouveau composant `PersonalizedDocumentCard` (même convention que les
composants existants) :
- États : génération en cours / prêt (avec bouton de téléchargement) / erreur
- Bandeau "relisez ce document avant de l'envoyer" toujours visible une fois
  le document prêt
- Badge "à vérifier" additionnel si `needs_review` est vrai (CV uniquement)

Une régénération remplace simplement l'affichage précédent — pas de gestion
de versions multiples côté UI.

Extensions :
- `lib/api.ts` : `generateCv`, `generateLetter`, `downloadCv`,
  `downloadLetter`
- `lib/types.ts` : type `PersonalizedDocument`

## Tests

- **Deterministic Verification** : tests unitaires sur des cas connus (nom
  d'employeur inventé → détecté ; nom réel reformulé → non signalé)
- **CV Rewriter / Cover Letter Generator** : réponse API Claude mockée en
  tests d'intégration — on teste le parsing/validation et l'intégration dans
  le flux, pas la qualité rédactionnelle du LLM (non déterministe, coûteux,
  hors scope des tests automatisés)
- **PDF Generator** : test que la génération ne lève pas d'erreur et produit
  un PDF non vide pour un contenu structuré donné
- **API (endpoints)** : tests d'intégration avec Claude et MinIO mockés,
  couvrant succès, rate-limit, diagnostic introuvable, échec LLM
- **RGPD** : test que `DELETE /diagnostics` purge bien les objets MinIO et
  les lignes `PersonalizedDocument` liées
- **Qualité de la réécriture** : comme pour le diagnostic (sous-projet 1),
  évaluation manuelle périodique sur un petit set de référence — pas de test
  automatisé sur la qualité rédactionnelle elle-même
- **Frontend** : tests légers de composants pour `PersonalizedDocumentCard`
  (mêmes conventions que l'existant — le risque principal reste côté backend
  et qualité du contenu généré, pas côté UI)

## Prochaines étapes (hors scope de cette spec)

- Sous-projet 2 : automatisation de candidature (recherche d'offres +
  soumission), qui pourra réutiliser les CV/lettres générés par ce
  sous-projet
