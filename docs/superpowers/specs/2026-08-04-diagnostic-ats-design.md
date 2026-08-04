# Diagnostic ATS — Design

## Contexte et vision globale

Le projet final vise à reproduire, en moins cher et en mieux, ce que propose une
plateforme comme Hirly : aider les candidats qualifiés qui se font rejeter par
les ATS (Applicant Tracking Systems) malgré leurs compétences. La vision
complète se décompose en trois sous-systèmes indépendants :

1. **Diagnostic ATS** (ce document) — analyser un CV par rapport à une offre,
   détecter les problèmes de parsing/format et les écarts de contenu.
2. **Automatisation de candidature** (futur) — rechercher des offres sur
   différentes plateformes et postuler automatiquement pour l'utilisateur.
3. **Personnalisation** (futur) — générer/adapter CV et lettres de motivation
   par offre.

Chaque sous-système sera conçu et livré séparément, avec sa propre spec. Ce
document couvre uniquement le **sous-projet 1 : Diagnostic ATS**, choisi comme
point de départ car il apporte de la valeur seul, sans dépendre des deux
autres, et sert de base technique à l'automatisation et la personnalisation
futures.

## Objectif de ce sous-projet

Permettre à un utilisateur de :
1. Uploader son CV (PDF ou DOCX)
2. Fournir une offre d'emploi précise (texte collé ou URL)
3. Obtenir un diagnostic : un score de compatibilité et une liste de problèmes
   concrets et actionnables expliquant pourquoi ce CV pourrait être mal traité
   par un ATS ou ne pas correspondre à l'offre

**Hors scope pour cette V1** (explicitement exclus, réservés à des itérations
futures) :
- Réécriture automatique du CV
- Génération de lettre de motivation
- Recherche automatique d'offres et candidature automatique
- Support de CV scannés (OCR)
- Facturation / paiement réel (structure de comptes prévue, mais gratuit et
  illimité pour cette V1)

## Utilisateurs cibles

Conçu dès le départ comme un produit potentiellement commercial et
multi-utilisateurs (le porteur du projet compte l'utiliser lui-même en
premier, dans sa recherche d'emploi actuelle, puis l'ouvrir à d'autres si
l'outil fait ses preuves — notamment en réaction au prix élevé des solutions
existantes comme Hirly).

Langues supportées : français et anglais (CV et offres).

## Architecture globale

```
┌─────────────────┐         ┌──────────────────────┐         ┌─────────────┐
│  Frontend        │  HTTP   │  Backend (FastAPI)     │         │  PostgreSQL │
│  Next.js/React    │◄──────►│                        │◄───────►│  (users,    │
│  - Auth (login)    │         │  - Auth (JWT)          │         │  diagnostics)│
│  - Upload CV        │         │  - Parsing CV          │         └─────────────┘
│  - Coller offre     │         │  - Scraping offre (URL)│
│  - Voir diagnostic  │         │  - Règles structurelles│         ┌─────────────┐
└─────────────────┘         │  - Analyse LLM (Claude) │────────►│  Claude API │
                              └──────────────────────┘         └─────────────┘
```

Stack :
- **Frontend** : Next.js/React (SPA/API-driven, séparé du backend)
- **Backend** : FastAPI (Python) — API pure, pas de rendu serveur
- **Base de données** : PostgreSQL (utilisateurs, historique des diagnostics)
- **LLM** : API Claude (modèle Haiku recommandé pour le coût, largement
  suffisant pour une analyse comparative de texte)

## Composants

### 1. Auth
Inscription/connexion par email + mot de passe, JWT pour les sessions, hash
bcrypt. Rien d'exotique, pas de conception poussée nécessaire ici.

### 2. CV Parser
- **Entrée** : fichier PDF ou DOCX uploadé
- **Sortie** : texte brut extrait + métadonnées structurelles (mise en page
  multi-colonnes, présence de tableaux, texte contenu dans des images,
  sections standards détectées ou absentes — Expérience, Formation,
  Compétences...)
- **Librairies** : `pdfplumber` ou `PyMuPDF` (PDF), `python-docx` (DOCX)
- **Cas limite** : CV scanné (image sans couche de texte) → texte extrait
  vide/quasi-vide → détecté et signalé comme non traitable en V1 (pas d'OCR)

### 3. Offer Ingestion
- **Entrée** : texte collé directement, ou URL
- **Sortie** : texte brut de l'offre
- Si URL : scraping (`httpx` + `BeautifulSoup`) ciblant le contenu principal
  de la page
- **Cas limite** : sites bloquant le scraping (anti-bot) ou contenu
  chargé en JS → si le scraping échoue ou renvoie un contenu vide/suspect,
  fallback propre demandant à l'utilisateur de coller le texte manuellement

### 4. Structural Rules Engine
- **Entrée** : métadonnées structurelles du CV Parser
- **Sortie** : score de "parsabilité" (0-100) + liste d'issues concrètes
  (ex: "mise en page 2 colonnes, souvent mal lue par les ATS", "aucune
  section 'Expérience' standard détectée")
- 100% déterministe, aucun appel externe — rapide, gratuit, testable
  unitairement, et facile à enrichir avec de nouvelles règles au fil du temps

### 5. Semantic Analyzer (LLM)
- **Entrée** : texte du CV + texte de l'offre
- **Sortie structurée** (via structured output/tool use de l'API Claude,
  validée par un modèle Pydantic — pas de parsing de texte libre) : score de
  correspondance (0-100), mots-clés/compétences présents dans l'offre mais
  absents du CV, recommandations actionnables
- Modèle recommandé : Claude Haiku
- Gère nativement le FR/EN sans pipeline NLP séparé par langue

### 6. Diagnostic Aggregator
- Combine le score de parsabilité (règles) et le score de correspondance
  (LLM) en un rapport final (score global = moyenne simple des deux scores
  dans un premier temps ; la pondération pourra être ajustée plus tard une
  fois qu'on aura des cas réels pour comparer)
- Sauvegarde le diagnostic en base (lié à l'utilisateur), le retourne au
  frontend

## Flux de données

1. Utilisateur connecté → upload CV (PDF/DOCX) + fournit l'offre (texte
   collé OU URL)
2. En parallèle : CV Parser extrait texte + métadonnées structurelles ;
   Offer Ingestion récupère le texte de l'offre (scraping si URL, fallback
   vers saisie manuelle si échec)
3. Structural Rules Engine analyse les métadonnées du CV → score de
   parsabilité + issues
4. Semantic Analyzer envoie (texte CV + texte offre) à Claude → score de
   correspondance + mots-clés manquants + recommandations
5. Diagnostic Aggregator combine les deux résultats → rapport final
6. Sauvegarde en base (liée à l'utilisateur) + retour au frontend
7. Frontend affiche le rapport complet

Traitement synchrone en une seule requête (pas de queue/job asynchrone
nécessaire pour cette V1, le traitement complet devrait prendre quelques
secondes).

**Confidentialité** : seuls le texte extrait et les métadonnées sont
conservés en base — jamais le fichier CV brut — afin de limiter la donnée
personnelle stockée.

## Gestion des erreurs et cas limites

**Upload CV**
- Format non supporté → rejet immédiat, message clair
- Fichier corrompu/illisible → erreur explicite, pas de crash silencieux
- CV scanné → message dédié expliquant que ce format n'est pas encore
  supporté
- Fichier trop volumineux (> 5 Mo) → rejet avec message clair

**Offre d'emploi**
- URL invalide/inaccessible → erreur explicite
- Scraping bloqué ou contenu vide/JS-rendu → fallback vers saisie manuelle,
  jamais d'échec silencieux avec une offre vide analysée comme si de rien
  n'était
- Texte collé non pertinent → accepté tel quel en V1 (problème de qualité du
  diagnostic, pas de robustesse technique — pas de détection fiable possible
  à ce stade)

**Appel LLM**
- Timeout/erreur API → un retry automatique, puis erreur propre à
  l'utilisateur plutôt qu'un rapport partiel
- Réponse ne respectant pas le format structuré attendu → validation
  Pydantic qui rejette et déclenche un retry, jamais de sauvegarde d'un
  diagnostic corrompu

**RGPD**
- L'utilisateur doit pouvoir supprimer son historique de diagnostics —
  nécessaire pour une conformité basique vu la nature personnelle des
  données (CV) et l'ambition commerciale en France/UE

**Abus / coût**
- Rate-limit léger par compte dès la V1 (ex: X diagnostics par heure), même
  sans quota produit (comptes gratuits illimités décidés pour cette V1) —
  objectif uniquement d'éviter qu'un abus ou un bug ne fasse exploser la
  facture API

## Tests

- **Structural Rules Engine** : tests unitaires sur un jeu de CV
  d'exemple avec des problèmes connus (colonnes, tableaux, sections
  absentes, texte en image) — sert aussi de garde-fou contre les
  régressions
- **CV Parser / Offer Ingestion** : tests unitaires sur fichiers réels (bons
  et mauvais cas) ; scraping testé avec mocks HTTP (page fonctionnelle,
  bloquée, vide) sans dépendre du réseau réel
- **Semantic Analyzer** : réponse API Claude mockée en tests d'intégration —
  on teste le parsing/validation Pydantic et l'intégration dans le flux, pas
  la qualité du LLM (non déterministe, coûteux, hors scope des tests
  automatisés)
- **Qualité du diagnostic** : évaluation manuelle périodique sur un petit
  set de référence (CV + offres réelles, avec problèmes connus) — pas un
  test automatisé, une vérification qualitative
- **API (endpoints FastAPI)** : tests d'intégration avec base de données de
  test, couvrant auth, upload, et le flux complet (LLM mocké)
- **Frontend** : tests légers pour cette V1 (tests manuels + éventuellement
  quelques tests de composants clés), le risque principal du projet étant
  côté backend et qualité du diagnostic, pas côté UI

## Prochaines étapes (hors scope de cette spec)

Une fois ce diagnostic validé et fiable, deux sous-projets pourront être
brainstormés et spécifiés séparément :
- Automatisation de candidature (recherche d'offres + soumission)
- Personnalisation (réécriture de CV, génération de lettre de motivation)
