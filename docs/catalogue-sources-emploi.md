# Catalogue des sources d'offres d'emploi — Search

> Roadmap des connecteurs / scrapers à développer pour l'agrégation d'offres.
> Priorité : **Sénégal d'abord**, puis Afrique de l'Ouest / Centrale francophone,
> remote, humanitaire/international.
>
> Dernière mise à jour : 2026-09-03. Établi à partir de recherches web +
> connaissance du terrain. Le **tier P0/P1 a été vérifié en réel le 2026-09-03**
> (curl avec User-Agent navigateur : `robots.txt`, `sitemap.xml`, endpoints
> d'API, comportement anti-bot) — voir [§0 Constats de vérification](#0-constats-de-vérification-p0p1--2026-09-03).
> Les valeurs `❓` restantes (tiers P2/P3) ne sont pas vérifiées.

---

## 0. Constats de vérification P0/P1 — 2026-09-03

Résultats des tests réels. **Trois surprises importantes.**

| Source | Constat | Impact |
|---|---|---|
| **ReliefWeb** ⚠️ | API **v1 décommissionnée depuis le 1ᵉʳ nov. 2025**. `v2` exige un **`appname` pré-approuvé** (formulaire Google, revue manuelle, gratuit). Le défaut `reliefweb_appname="ats-diagnostic-search"` renvoie **403** → **la source est muette en prod aujourd'hui**. Le code (`reliefweb.py`) est déjà en v2, seul l'appname manque. | **Action requise** : demander un appname sur https://apidoc.reliefweb.int/parameters#appname puis remplir `RELIEFWEB_APPNAME`. Tant que ce n'est pas fait, retirer ReliefWeb des sources actives ou l'accepter en `unavailable_sources`. |
| **Réseau AfricaWork** ⚠️ (emploisenegal.com, emploi.ci, emploi.cm) | **Cloudflare "challenge" (Turnstile/JS) sur TOUTES les URLs**, y compris `/robots.txt` → **403 "Just a moment"** pour tout client non-navigateur, même avec en-têtes navigateur complets. Non contournable sans navigateur headless (Playwright). Leur « Recruitment API » est côté **publication** d'offres, pas consultation. | **Rétrogradé P1 → P3 / bloqué.** Ne pas investir : coût élevé (headless), fragile, hostile. Le sitemap n'est même pas atteignable. |
| **Careerjet** ⚠️ | L'**API legacy est fermée** ("only accessible for authenticated legacy users"). Nouvelle **API v4** : `https://search.api.careerjet.net/v4/query`, **Basic auth** (clé API par site éditeur, obtenue via un compte Publisher), en-tête `Referer` obligatoire, params `user_ip` + `user_agent` requis, GET → JSON, `page_size` 1-100. La **couverture Afrique francophone n'est pas documentée** (liste des `locale_code` non publiée). | Toujours **P0** mais : (1) créer un compte Publisher Careerjet, (2) **tester une vraie clé sur `fr_SN`, `fr_CI`, `fr_CM`** avant de compter dessus. Si le volume Afrique est faible → rétrograder P2. |
| **UN Talent** (untalent.org) | API **JSON + RSS confirmée**, filtres `areas`/`locations`/`homebased`/`contract types`/`job levels`/`companies`. **Gratuit en fair-use avec attribution**, mais **sur demande d'accès** (endpoint non public, fourni après « Request access »). Fraîcheur **inégale** selon la source (World Bank : 2 h ; UNDP / AfDB : ~1 an). Couverture ONU/IGO/INGO mondiale, Afrique incluse mais non ciblée. Fallback : pages HTML `untalent.org/jobs/in-anything/contract-*/anywhere` **sont** rendues serveur (scrapables). | **P0 → P1** (accès gated + fraîcheur variable). Demander l'accès ; en attendant, le fallback HTML est possible. |
| **Senjob** ✅ | `robots.txt` **200**, Apache. Disallow limité aux pages CV/employeur/`/abonnes/prix.html` ; bloc `googlebot` qui **autorise explicitement `/*/jobseekers/voir_offre.php`** (pages d'offre). Listing `/sn/offres-d-emploi.php` → **200, 141 Ko** HTML rendu serveur. `sitemap.xml` → **404**. Pas de RSS. `Sitemap:` dans robots pointe vers un sitemap absent. | **crawl, Moyen.** P1 confirmé. Préfixe pays `/sn/`, `/ci/`… ; parser les cartes du listing + `voir_offre.php`. |
| **Novojob** ✅ | Site **Joomla**. `robots.txt` = défaut Joomla (rien de bloquant sur les offres). `sitemap.xml` **redirige** vers `/senegal/` (pas de vrai sitemap). Listing `/senegal/offres-d-emploi` → **200, 52 Ko** rendu serveur. Réseau multi-pays par segment d'URL `/{pays}/`. | **crawl, Moyen.** P1 confirmé. |
| **Educarriere.ci** ✅ | `emploi.educarriere.ci/` → **200, 343 Ko** rendu serveur (offres dans le HTML). Pas de `robots.txt` (404), pas de `sitemap.xml` (404) → aucune restriction déclarée. | **crawl, Moyen.** P1 confirmé. Vérifier les CGU du site avant activation. |
| **RemoteOK** ✅ | `https://remoteok.com/api` → **200, JSON ~430 Ko, sans clé**. Flux RSS aussi. | **live, Facile.** P1 confirmé, quasi zéro effort. Attribution demandée par leurs CGU. |
| **Remotive** ✅ | `https://remotive.com/api/remote-jobs` → **200, JSON ~200 Ko, sans clé**. | **live, Facile.** P1 confirmé, quasi zéro effort. |
| **Jobicy** ✅ | `https://jobicy.com/api/v2/remote-jobs` → **200 JSON**. Déjà intégré, OK. | RAS. |
| **Emploi Dakar** ✅ | `robots.txt` = WordPress (bloque `/CV/`, `/resume/`, MauiBot ; offres OK). `sitemap.xml` → `sitemap_index.xml` **200**. Déjà intégré via sitemap. | RAS. |
| **Adzuna** | Couverture Afrique = **Afrique du Sud (`za`) uniquement**. Aucun pays d'Afrique francophone. Déjà intégré (`fr`). | Activer `za` marginal pour la cible Sénégal ; faible priorité. |

### Ce qu'il faut faire maintenant (issu des constats)

1. **ReliefWeb** — demander un `appname` approuvé (sinon la source est déjà cassée en prod).
2. **Careerjet** — ouvrir un compte Publisher, tester une clé réelle sur les locales `fr_SN` / `fr_CI` / `fr_CM`, mesurer le volume avant de s'engager.
3. **UN Talent** — envoyer la demande d'accès API (fair-use gratuit).
4. **RemoteOK + Remotive** — intégrables tout de suite, aucune clé (S1).
5. **Senjob / Novojob / Educarriere.ci** — 3 crawlers `crawl`, markup à snapshoter dans les fixtures.
6. **AfricaWork** — abandonner pour l'instant (Cloudflare). Ré-évaluer si un jour on a un pool de navigateurs headless.

---

## Légende

| Colonne | Valeurs |
|---|---|
| **Accès** | 🟢 offres visibles sans compte (compte éventuel seulement pour postuler) · 🟡 une partie visible, reste derrière login · 🔴 login obligatoire pour voir les offres |
| **Postuler** | `ext` redirection vers un site tiers / e-mail · `compte` compte requis sur la plateforme · `?` inconnu |
| **API** | ✅ API publique exploitable · 🔑 API sur clé/partenariat · ❌ aucune · ❓ non vérifié |
| **RSS** | ✅ flux exploitable · ❌ absent · ❓ non vérifié |
| **Scrap.** | Facile (HTML statique / sitemap) · Moyen (pagination, markup irrégulier) · Difficile (Cloudflare / anti-bot / rendu JS) |
| **Fiab.** | ●●● stable + volume + fraîcheur · ●● correct · ● irrégulier / faible volume |
| **Prio** | **P0** socle immédiat · **P1** vague suivante, fort ROI · **P2** utile, effort moyen · **P3** niche / plus tard |
| **État** | ✅ intégré · 🔨 en cours · ⬜ à faire |

**Familles techniques** (cf. `docs/superpowers/specs/2026-08-28-sources-afrique-ouest-design.md`) :
- **live** → module implémentant le `Protocol` `SearchClient` dans `backend/app/job_search/`, interrogé à chaque recherche (API ou flux + cache mémoire).
- **crawl** → crawler périodique dans `job_search/crawlers/`, upsert dans `crawled_listing`, lu via `CrawledListingClient`.

---

## 1. Socle immédiat — P0

Sources à haute fiabilité, API/flux propres, faible coût d'intégration. La
plupart sont **déjà branchées** ; les deux ajouts (Careerjet, UN Talent)
valent le détour.

| Pays | Organisme | URL | Famille | Accès | Postuler | API | RSS | Scrap. | Fiab. | État |
|---|---|---|---|---|---|---|---|---|---|---|
| Multi (FR + Europe) | France Travail | francetravail.io | live | 🟢 | ext | 🔑 | ❌ | — | ●●● | ✅ |
| Afrique du Sud + monde | Adzuna | developer.adzuna.com | live | 🟢 | ext | 🔑 | ❌ | — | ●●● | ✅ (`fr`) — Afrique = `za` seulement |
| Multi (agrégateur) | **Careerjet** | careerjet.com/partners/api | live | 🟢 | ext | 🔑 API v4, Basic auth, clé Publisher, en-tête `Referer` requis, JSON | ❌ (v4) | Facile (API) | ●● | ⬜ (tester couverture Afrique) |
| Mondial / humanitaire | ReliefWeb (OCHA) | api.reliefweb.int/**v2**/jobs | live | 🟢 | ext | ✅ **appname pré-approuvé requis** (gratuit, sur formulaire) | ✅ | Facile | ●●● | ⚠️ code OK, **appname non approuvé → 403** |
| Mondial / ONU-ONG | **UN Talent** | untalent.org/open | live | 🟢 | ext | ✅ JSON + RSS, **sur demande d'accès**, fair-use gratuit + attribution | ✅ | Facile | ●● (fraîcheur inégale) | ⬜ (demander l'accès) |
| Mondial / remote | Jobicy | jobicy.com/jobs-rss-feed | live | 🟢 | ext | ✅ (`/api/v2/remote-jobs`) | ✅ | Facile | ●● | ✅ |
| Mondial / remote | **RemoteOK** | remoteok.com/api | live | 🟢 | ext | ✅ JSON **sans clé** | ✅ | Facile | ●● | ⬜ (S1, trivial) |
| Mondial / remote | **Remotive** | remotive.com/api/remote-jobs | live | 🟢 | ext | ✅ JSON **sans clé** | ✅ | Facile | ●● | ⬜ (S1, trivial) |
| Sénégal | **Emploi Dakar** | emploidakar.com | crawl | 🟢 | ext / compte | ❌ | ❌ | Moyen (`sitemap_index.xml` OK) | ●●● | ✅ |

**Careerjet** — après vérification, moins évident que prévu : l'API legacy est
fermée, la v4 impose une clé Publisher + `Referer`, et **la couverture des
pays d'Afrique francophone n'est pas documentée**. Reste P0 *conditionnel* :
ouvrir un compte Publisher, tester `fr_SN` / `fr_CI` / `fr_CM` avec une vraie
clé, mesurer le volume. Bon repli si le volume tient ; sinon P2. C'est un
agrégateur → dédup par URL (les liens Careerjet sont des redirections → à
résoudre/normaliser).

**UN Talent** (untalent.org) : API JSON + RSS confirmée, filtres `areas`,
`locations`, `homebased`, `contract_types`, `job_levels`, `companies`.
Gratuit en fair-use avec attribution, **mais l'endpoint est fourni après une
demande d'accès**. Fraîcheur inégale selon l'agence source. Fallback possible :
les pages `untalent.org/jobs/in-anything/contract-*/anywhere` sont rendues
serveur donc scrapables. Recouvre partiellement ReliefWeb, ratisse plus large
côté ONU/IGO.

**RemoteOK / Remotive** : les deux exposent une API JSON publique **sans
clé** — intégration `SearchClient` triviale, à faire en S1. Attribution
demandée par leurs CGU (garder titre + lien).

---

## 2. Vague suivante — P1

Fort intérêt pour un candidat sénégalais, effort d'intégration modéré.

### 2a. Job boards Sénégal

| Organisme | URL | Famille | Accès | Postuler | API | RSS | Scrap. | Fiab. | Prio | État |
|---|---|---|---|---|---|---|---|---|---|---|
| **Senjob** | senjob.com/sn/offres-d-emploi.php | crawl | 🟢 | compte / ext | ❌ | ❌ | Moyen (Apache/PHP, rendu serveur, pagination, préfixe pays `/sn/`, `robots` autorise `voir_offre.php`) | ●●● | P1 | ⬜ |
| **Novojob Sénégal** | novojob.com/senegal | crawl | 🟢 | compte / ext | ❌ | ❌ | Moyen (Joomla, rendu serveur, pas de sitemap) | ●● | P1 | ⬜ |
| ~~EmploiSenegal.com (AfricaWork)~~ | emploisenegal.com | — | 🔴 | compte | ❌ (côté conso) | ❌ | **Bloqué** — Cloudflare challenge JS sur toutes les URLs | ●●● | ~~P1~~ → **P3** | ⛔ |

> **Senjob** et **Novojob** couvrent plusieurs pays francophones avec la même
> plateforme → un crawler paramétré par préfixe/segment pays sert tout le
> réseau. Les deux sont en **rendu serveur**, sans sitemap ni RSS : parser les
> cartes du listing paginé + la page de détail.
>
> **AfricaWork est abandonné** (vérif 2026-09-03) : Cloudflare renvoie un
> challenge JS (« Just a moment ») même sur `/robots.txt`, non contournable
> sans navigateur headless. Voir [§0](#0-constats-de-vérification-p0p1--2026-09-03).

### 2b. Réseau Novojob — un connecteur, Afrique de l'Ouest

`novojob.com/<pays>/…` (Joomla, rendu serveur, pas de sitemap — vérifié SN).
Sénégal, Côte d'Ivoire, Bénin, Togo, Burkina, Mali, Niger, Guinée. Un crawler
paramétré par segment pays.

| Pays | URL | Prio |
|---|---|---|
| Sénégal | novojob.com/senegal | P1 |
| Côte d'Ivoire | novojob.com/cote-d-ivoire | P1 |
| Bénin | novojob.com/benin | P2 |
| Togo | novojob.com/togo | P2 |
| Burkina / Mali / Niger / Guinée | novojob.com/{pays} | P2 |

### 2c. Côte d'Ivoire

| Organisme | URL | Famille | Accès | API | RSS | Scrap. | Fiab. | Prio |
|---|---|---|---|---|---|---|---|---|
| **Educarriere.ci** | emploi.educarriere.ci | crawl | 🟢 | ❌ | ❌ | Moyen (rendu serveur, pas de robots/sitemap → vérifier CGU) | ●●● | P1 |
| RMO Jobcenter (cabinet, multi-pays) | rmo-jobcenter.com | crawl | 🟢 | ❌ | ❓ | Moyen | ●● | P2 |
| Offre-emploi.ci | offre-emploi.ci | crawl | 🟢 | ❓ | ❓ | Moyen | ●● | P2 |

### 2d. Humanitaire / ONG / remote (déjà partiellement en place)

| Organisme | URL | Famille | Accès | API | RSS | Scrap. | Fiab. | Prio | État |
|---|---|---|---|---|---|---|---|---|---|
| NGO Jobs in Africa | ngojobsinafrica.com | live (RSS + cache) | 🟢 | ❌ | ✅ (`/media-rss/`, flux par pays) | Facile | ●● | P1 | ✅ |
| We Work Remotely | weworkremotely.com/remote-jobs.rss | live (RSS) | 🟢 | ❌ | ✅ | Facile | ●● | P1 | ✅ |
| RemoteOK | remoteok.com/api | live | 🟢 | ✅ JSON **sans clé** (vérifié) | ✅ | Facile | ●● | P1 | ⬜ |
| Remotive | remotive.com/api/remote-jobs | live | 🟢 | ✅ JSON **sans clé** (vérifié) | ✅ | Facile | ●● | P1 | ⬜ |

---

## 3. Utile — P2

### 3a. Cameroun / Bénin / Togo — boards nationaux hors réseau

| Pays | Organisme | URL | Accès | API | RSS | Scrap. | Fiab. | Prio |
|---|---|---|---|---|---|---|---|---|
| Cameroun | Minajobs | minajobs.net | 🟢 | ❌ | ❓ (probable, moteur type forum/CMS) | Moyen | ●● | P2 |
| Cameroun | Prosyjob | prosyjob.com | 🟢 | ❌ | ❓ | Moyen | ● | P3 |
| Bénin | ANPE Bénin | anpe.bj | 🟢 | ❌ | ❌ | Moyen | ● | P3 |
| Togo | ANPE Togo | anpetogo.org | 🟢 | ❌ | ❌ | Moyen | ● | P3 |
| Togo | L'Ucréatif | lucreatif.com | 🟢 | ❌ | ❓ | Moyen | ● | P3 |

### 3b. Sénégal — secteur public & institutionnel

| Organisme | URL | Type | Accès | Scrap. | Fiab. | Prio |
|---|---|---|---|---|---|---|
| ANPEJ | anpej.sn | Agence nationale pour l'emploi des jeunes | 🟢 | Moyen | ●● | P2 |
| Fonction Publique | fonctionpublique.gouv.sn | Concours & recrutements administration | 🟢 | Moyen | P2 |
| concoursn.com | concoursn.com | Agrégateur concours/offres (WordPress → RSS probable) | 🟢 | Facile | ●● | P2 |
| Sociumjob | sociumjob.com | Job board Afrique (dispose d'une v2 `dev-v2`) | 🟢 | ❓ API | Moyen | ●● | P2 |

### 3c. Agrégateurs pan-africains / feeds partenaires

| Organisme | URL | Accès | API | RSS | Scrap. | Fiab. | Prio |
|---|---|---|---|---|---|---|---|
| Jooble | jooble.org (`sn.jooble.org`, …) | 🟢 | 🔑 (API partenaire / affiliation) | ❌ | Moyen | ●● | P2 |
| Talent.com | talent.com | 🟢 | 🔑 (feed partenaire) | ❌ | Moyen | ●● | P2 |
| MyJobMag | myjobmag.com (NG, KE, GH, ZA) | 🟢 | ❌ | ✅ (probable, CMS) | Moyen | ●● | P2 |
| Jobberman (ROAM) | jobberman.com (NG, GH) | 🟢 | ❌ | ❓ | Moyen | ●● | P2 |
| BrighterMonday (ROAM) | brightermonday.com (KE, UG, TZ) | 🟢 | ❌ | ❓ | Moyen | ● | P3 |
| Impactpool | impactpool.org | 🔴 (compte pour voir la plupart) | ❌ (scraping tiers payant) | ❌ | Difficile | ●● | P2 |
| UNjobs.org / uncareer.net | unjobs.org | 🟢 | ❌ | ✅ (probable) | Facile | ●● | P2 |
| AfDB / Banque Africaine de Dév. | afdb.org/en/about-us/careers | 🟢 | ❌ | ❓ | Moyen (SAP SuccessFactors) | ●● | P2 |
| UNDP | jobs.undp.org | 🟢 | ❌ | ❓ | Moyen | ●● | P2 |

### 3d. Remote (complément)

| Organisme | URL | API | RSS | Prio |
|---|---|---|---|---|
| Remotive | remotive.com/api/remote-jobs | ✅ (JSON public) | ✅ | P2 |
| Working Nomads | workingnomads.com | ❌ | ✅ | P3 |
| Remote OK | (voir P1) | ✅ | ✅ | P1 |

---

## 4. Niche / plus tard — P3

| Pays / portée | Organisme | URL | Note |
|---|---|---|---|
| Sénégal | Jobartis Sénégal | jobartis.sn | Réseau Jobartis (multi-pays), volume modéré |
| Sénégal | iWorks / freelances | iworks.sn | Freelance, hors cœur de cible salarié |
| Guinée | DigiJob Guinée | digijobguinee.com | Blog-annuaire, faible volume |
| Guinée | Guineejob | guineejob.com | Réseau AfricaWork-like à confirmer |
| Burkina | Emploiburkina / Bnjobs | — | Faible volume |
| RDC | MediaCongo Emploi | mediacongo.net | Rubrique emploi d'un portail news |
| RDC | Radio Okapi | radiookapi.net | Annonces ONU/ONG RDC |
| Pan-Afrique | AfriqueJob | afriquejob.com | Annuaire de sites, pas d'offres directes → source de découverte, pas connecteur |
| Pan-Afrique | Afri-Emploi | afri-emploi.com | Cadres, volume faible |
| Pan-Afrique | JobAfrique | jobafrique.com | Ancien, fraîcheur douteuse |
| Exécutif | Michael Page Africa | michaelpageafrica.com | Cadres dirigeants, niche |
| Diaspora | Talent2Africa | talent2africa.com | Cadres/diaspora, compte requis pour le détail — P2 si cible cadres |
| Régional | BCEAO / BOAD / UEMOA / CEDEAO | — | Institutions ; volume très faible, publication irrégulière |
| Mondial | Devex | devex.com | Développement international ; mur payant |
| Mondial | Google Jobs | — | Pas d'API officielle ; nécessite SerpAPI (payant) — éviter |
| Interdit | LinkedIn | — | **Exclu** : CGU + jurisprudence *hiQ*. Le chemin « coller une URL d'offre » couvre le besoin ponctuel. |

---

## 5. Roadmap connecteurs proposée

| Sprint | Contenu | Famille | Gain |
|---|---|---|---|
| **S0 (démarches, hors code)** | Demander l'`appname` **ReliefWeb** approuvé · ouvrir un compte **Careerjet Publisher** + tester une clé sur `fr_SN`/`fr_CI`/`fr_CM` · envoyer la demande d'accès **UN Talent** | — | Débloque 3 sources ; ReliefWeb est **déjà cassée** en prod sans ça |
| **S1** | **RemoteOK + Remotive** (clients `SearchClient` JSON, sans clé) | live | Remote first-class, ~0 risque, aucune démarche |
| **S2** | **Careerjet** v4 (si le test S0 est concluant) · **UN Talent** (client JSON, si accès obtenu) | live | Couverture agrégée francophone + ONU |
| **S3** | Crawler **Senjob** (préfixe pays `/sn/`, `/ci/`…) | crawl | Board national #1 bis, multi-pays |
| **S4** | Crawler **Educarriere.ci** | crawl | Board CI à fort trafic |
| **S5** | Crawler **réseau Novojob** paramétré : SN, CI, BJ, TG | crawl | 1 connecteur → 4 pays |
| **S6** | Sénégal public : ANPEJ, Fonction Publique, concoursn.com | crawl | Secteur public / concours |
| **S7+** | Minajobs (CM), MyJobMag RSS, Jooble/Talent.com feeds partenaires, AfDB/UNDP | mixte | Élargissement |

> **AfricaWork** ne figure plus dans la roadmap : Cloudflare challenge JS
> (vérifié 2026-09-03). À reconsidérer seulement si un pool de navigateurs
> headless est mis en place pour d'autres besoins.

### Checklist de qualification d'une source (à faire avant chaque connecteur)

1. `curl -A "Mozilla/5.0 …" https://SITE/robots.txt` — crawl autorisé ? délai ?
2. Chercher `/sitemap.xml`, `/sitemap_index.xml`, `/feed`, `/rss`, `/jobs.rss`, `/api`.
3. Vérifier les CGU : interdiction explicite du scraping / de la réutilisation ?
4. Offres visibles sans compte ? (tester en navigation privée)
5. Markup : cartes d'offres parsables en HTML statique, ou rendu JS (→ besoin navigateur headless, coût) ?
6. Volume & fraîcheur : nombre d'offres actives, date de la plus récente.
7. Anti-bot : Cloudflare « Just a moment », 403 sur UA non-navigateur, rate-limit agressif ?
8. Décision : **live** (API/RSS) · **crawl** (HTML tolérant) · **désactivé** (CGU hostiles ou anti-bot bloquant) — inscrire dans `enabled_crawlers` seulement si 1–3 OK.

### Config à prévoir (`backend/app/config.py`)

```python
reliefweb_appname: str = ""          # ⚠️ DOIT être un appname APPROUVÉ (v1 morte, v2 refuse les autres)
careerjet_api_key: str = ""          # clé Publisher Careerjet (Basic auth), + referer requis à l'appel
un_talent_api_key: str = ""          # jeton fourni après demande d'accès ; attribution obligatoire
remoteok_enabled: bool = True
remotive_enabled: bool = True
# enabled_crawlers : ajouter au fil de l'eau
#   "senjob:sn", "senjob:ci", "educarriere_ci",
#   "novojob:sn", "novojob:ci", "novojob:bj", "novojob:tg",
#   "anpej", "fonction_publique_sn"
#   (PAS africawork:* — Cloudflare challenge, cf. §0)
```

---

## 6. Synthèse par priorité

- **P0 (8)** : France Travail ✅, Adzuna ✅ (`fr`), Jobicy ✅, Emploi Dakar ✅, **RemoteOK ⬜**, **Remotive ⬜**, ReliefWeb ⚠️ (appname à approuver), **Careerjet ⬜** (couverture Afrique à confirmer), **UN Talent ⬜** (accès à demander)
- **P1 (~7)** : Senjob, Novojob (SN/CI), Educarriere.ci, NGO Jobs ✅, WWR ✅
- **P2 (~14)** : Novojob (BJ/TG/BF/ML/NE/GN), Minajobs, RMO, Offre-emploi.ci, ANPEJ, Fonction Publique SN, concoursn, Sociumjob, Jooble, Talent.com, MyJobMag, Jobberman, Impactpool, UNjobs, AfDB, UNDP
- **P3 (~16)** : **AfricaWork réseau (Cloudflare)**, Jobartis, iWorks, DigiJob Guinée, Guineejob, MediaCongo, Radio Okapi, AfriqueJob, Afri-Emploi, JobAfrique, Michael Page, Talent2Africa, institutions régionales, Devex, Working Nomads
- **Exclu** : LinkedIn, Google Jobs (sans budget SerpAPI)

---

## Sources de la recherche

- [Emploi Dakar](https://www.emploidakar.com/) · [EmploiSenegal.com / AfricaWork](https://www.emploisenegal.com/) · [Senjob](https://senjob.com/sn/offres-d-emploi.php) · [Senego — sites recrutement Sénégal](https://senego.com/services/offres-emploi) · [Xarala — 5 plateformes emploi Sénégal](https://www.xarala.co/blog/5-plateformes-pour-trouver-un-emploi-rapidement-au-senegal-et-en-afrique/)
- [Socium — comparatif sites Afrique francophone 2026](https://sociumjob.com/medias/articles/meilleurs-sites-pour-postuler-en-afrique-francophone-le-comparatif-2026) · [Thot Cursus — répertoire sites emploi Afrique francophone](https://cursus.edu/fr/11623/repertoire-des-sites-doffres-demploi-maghreb-et-afrique-francophone) · [DigiJob Guinée — sites emploi Afrique de l'Ouest](https://digijobguinee.com/post.php?lang=fr&t=Les-Sites-D-offres-D-emploi-des-Pays-Francophones-En-Afrique-de-L-ouest&id=1122) · [ZeroName — top 10 plateformes emploi Afrique 2026](https://zeroname.space/ressources/top-10-plateformes-emploi-afrique)
- [Careerjet API (PublicAPIs.io)](https://publicapis.io/careerjet-api) · [Cavuno — job feeds 2026 (Jooble/Careerjet/Talent.com)](https://cavuno.com/blog/job-feeds) · [Apify — Africa Jobs Scraper (Jobberman/BrighterMonday/Careers24/MyJobMag)](https://apify.com/jungle_synthesizer/africa-jobs-aggregator-scraper) · [Kenyajob — Job API](https://www.kenyajob.com/job-api)
- [ReliefWeb API — paramètre appname (v1 décommissionnée, appname pré-approuvé)](https://apidoc.reliefweb.int/parameters#appname) · [ReliefWeb — flux RSS](https://reliefweb.int/rss) · [Careerjet Partners API v4](https://www.careerjet.com/partners/api/) · [UN Talent — open project (API/RSS)](https://untalent.org/open) · [NGO Jobs in Africa](https://ngojobsinafrica.com/) · [The M&E Specialist — 15 best development job boards](https://themandespecialist.com/15-best-job-boards-international-development/)
- [Novojob West Africa (LinkedIn)](https://www.linkedin.com/company/novojobwa) · [Talent2Africa](https://talent2africa.com/) · [AfricaWork — emploi.cf](https://www.emploi.cf/) · [UNDP Jobs — région Afrique](https://jobs.undp.org/cj_view_jobs.cfm?cur_rgn_id_c=RAF)
