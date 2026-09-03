# Catalogue des sources d'offres d'emploi — Search

> Roadmap des connecteurs / scrapers à développer pour l'agrégation d'offres.
> Priorité : **Sénégal d'abord**, puis Afrique de l'Ouest / Centrale francophone,
> remote, humanitaire/international.
>
> Dernière mise à jour : 2026-09-03. Établi à partir de recherches web +
> connaissance du terrain. Les colonnes **API** et **RSS** marquées `❓` n'ont
> **pas** été vérifiées en conditions réelles (curl avec vrai User-Agent,
> lecture de `/robots.txt`, `/sitemap.xml`, `/feed`) — c'est le premier travail
> à faire sur chaque source P0/P1 avant d'écrire le connecteur.

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
| Afrique du Sud + monde | Adzuna | developer.adzuna.com | live | 🟢 | ext | 🔑 | ❌ | — | ●●● | ✅ (FR) — activer `za` |
| Multi Afrique francophone | **Careerjet** | www.careerjet.fr/partners | live | 🟢 | ext | 🔑 (clé gratuite, 1000 req/h, JSON+XML) | ✅ | Facile (API) | ●●● | ⬜ |
| Mondial / humanitaire | ReliefWeb (OCHA) | reliefweb.int/help / /rss | live | 🟢 | ext | ✅ (`api.reliefweb.int/v1/jobs`, pas de clé, `appname`) | ✅ | Facile | ●●● | ✅ |
| Mondial / ONU-ONG | **UN Talent** | untalent.org/open | live | 🟢 | ext | ✅ (JSON, fair-use gratuit + attribution) | ✅ | Facile | ●●● | ⬜ |
| Mondial / remote | Jobicy | jobicy.com/jobs-rss-feed | live | 🟢 | ext | ✅ (`/api/v2/remote-jobs`) | ✅ | Facile | ●● | ✅ |
| Sénégal | **Emploi Dakar** | emploidakar.com | crawl | 🟢 | ext / compte | ❌ | ❓ | Moyen (sitemap.xml OK) | ●●● | ✅ |

**Careerjet** est le meilleur ratio effort/couverture pour l'Afrique
francophone : domaines pays (`careerjet.sn`, `.ci`, `.cm`, `.bj`, `.tg`,
`.ml`, `.bf`, `.ne`, `.cg`, `.ga`…), une seule clé, réponse JSON structurée,
rate-limit 1000/h large. C'est lui-même un agrégateur — attention aux
doublons avec les sources natives (dédup par URL déjà en place dans
`aggregator.py`, mais les URLs Careerjet sont des redirections → prévoir une
normalisation / résolution d'URL).

**UN Talent** (untalent.org) : API JSON + RSS, filtres `areas`, `locations`,
`homebased`, `contract_types`, `job_levels`, `companies`. Gratuit en fair-use
avec attribution (garder les liens de candidature). Recouvre partiellement
ReliefWeb mais ratisse plus large côté ONU/IGO.

---

## 2. Vague suivante — P1

Fort intérêt pour un candidat sénégalais, effort d'intégration modéré.

### 2a. Job boards Sénégal

| Organisme | URL | Famille | Accès | Postuler | API | RSS | Scrap. | Fiab. | Prio | État |
|---|---|---|---|---|---|---|---|---|---|---|
| Senjob | senjob.com/sn/offres-d-emploi.php | crawl | 🟢 | compte / ext | ❓ | ❓ | Moyen (PHP, pagination, préfixe pays `/sn/`) | ●●● | P1 | ⬜ |
| EmploiSenegal.com (réseau AfricaWork) | emploisenegal.com | crawl | 🟡 (login pour certaines offres) | compte | 🔑 (« Recruitment API » côté publication) | ❓ | **Difficile** (Cloudflare, 403 sur UA non-navigateur) | ●●● | P1 | ⬜ |
| Novojob Sénégal | novojob.com/senegal | crawl | 🟢 | compte / ext | ❓ | ❓ | Moyen | ●● | P1 | ⬜ |

> Senjob et le réseau AfricaWork couvrent **plusieurs pays francophones avec
> la même plateforme** → un crawler paramétré par domaine/préfixe pays sert
> tout le réseau (cf. §2b, §3). AfricaWork bloque agressivement les bots :
> prévoir un vrai User-Agent navigateur, un débit lent, et se rabattre sur le
> sitemap si accessible ; sinon rester désactivé (`enabled_crawlers`).

### 2b. Réseau AfricaWork — un connecteur, ~15 pays

Même moteur (Drupal + Solr, URLs `im_field_offre_*`), donc **un seul crawler
paramétré par domaine**. `kenyajob.com` expose une page « Job API » /
« Recruitment API » → vérifier si un flux de consultation existe (sinon crawl).

| Pays | Domaine | Prio |
|---|---|---|
| Sénégal | emploisenegal.com | P1 |
| Côte d'Ivoire | emploi.ci | P1 |
| Cameroun | emploi.cm | P1 |
| Bénin | emploi.bj | P2 |
| Togo | emploi.tg | P2 |
| Burkina Faso | emploi.bf | P2 |
| Mali | emploi.ml | P2 |
| Niger | emploi.ne | P2 |
| Guinée | emploi.gn | P2 |
| Gabon | emploi.ga | P2 |
| Congo | emploi.cg | P2 |
| RDC | emploi.cd | P2 |
| Centrafrique | emploi.cf | P3 |
| Kenya (anglophone, test API) | kenyajob.com | P2 |

### 2c. Réseau Novojob — un connecteur, Afrique de l'Ouest

`novojob.com/<pays>/…`. Sénégal, Côte d'Ivoire, Bénin, Togo, Burkina, Mali,
Niger, Guinée. Un crawler paramétré par segment pays.

### 2d. Côte d'Ivoire

| Organisme | URL | Famille | Accès | API | RSS | Scrap. | Fiab. | Prio |
|---|---|---|---|---|---|---|---|---|
| Educarriere.ci | emploi.educarriere.ci | crawl | 🟢 | ❓ | ❓ | Moyen | ●●● | P1 |
| RMO Jobcenter (cabinet, multi-pays) | rmo-jobcenter.com | crawl | 🟢 | ❌ | ❓ | Moyen | ●● | P2 |
| Offre-emploi.ci | offre-emploi.ci | crawl | 🟢 | ❓ | ❓ | Moyen | ●● | P2 |

### 2e. Humanitaire / ONG (déjà partiellement en place)

| Organisme | URL | Famille | Accès | API | RSS | Scrap. | Fiab. | Prio | État |
|---|---|---|---|---|---|---|---|---|---|
| NGO Jobs in Africa | ngojobsinafrica.com | live (RSS + cache) | 🟢 | ❌ | ✅ (`/media-rss/`, flux par pays) | Facile | ●● | P1 | ✅ |
| We Work Remotely | weworkremotely.com/remote-jobs.rss | live (RSS) | 🟢 | ❌ | ✅ | Facile | ●● | P1 | ✅ |
| RemoteOK | remoteok.com/api | live | 🟢 | ✅ (JSON public) | ✅ | Facile | ●● | P1 | ⬜ |

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
| **S1** | Careerjet (clé + client `SearchClient` JSON) · UN Talent (client JSON) | live | Couverture francophone multi-pays + ONU immédiate, ~0 risque |
| **S2** | RemoteOK + Remotive (clients JSON) · activer Adzuna `za` | live | Remote first-class complété |
| **S3** | Crawler **Senjob** (préfixe pays) · crawler **Educarriere.ci** | crawl | 2 boards nationaux à fort trafic |
| **S4** | Crawler **réseau AfricaWork** paramétré (test API `kenyajob`, sinon sitemap) : SN, CI, CM | crawl | 1 connecteur → 3 pays, extensible à ~12 |
| **S5** | Crawler **réseau Novojob** paramétré : SN, CI, BJ, TG | crawl | 1 connecteur → 4 pays |
| **S6** | Sénégal public : ANPEJ, Fonction Publique, concoursn.com | crawl | Secteur public / concours |
| **S7+** | Minajobs (CM), MyJobMag RSS, Jooble/Talent.com feeds partenaires, AfDB/UNDP | mixte | Élargissement |

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
careerjet_affid: str = ""                     # clé partenaire Careerjet
un_talent_appname: str = "search-app"          # attribution UN Talent
remoteok_enabled: bool = True
remotive_enabled: bool = True
# enabled_crawlers : ajouter au fil de l'eau
#   "senjob", "educarriere_ci",
#   "africawork:sn", "africawork:ci", "africawork:cm",
#   "novojob:sn", "novojob:ci", "novojob:bj", "novojob:tg",
#   "anpej", "fonction_publique_sn"
```

---

## 6. Synthèse par priorité

- **P0 (7)** : France Travail ✅, Adzuna ✅, ReliefWeb ✅, Jobicy ✅, Emploi Dakar ✅, **Careerjet ⬜**, **UN Talent ⬜**
- **P1 (~12)** : Senjob, AfricaWork (SN/CI/CM), Novojob (SN/CI), Educarriere.ci, NGO Jobs ✅, WWR ✅, RemoteOK, Remotive
- **P2 (~15)** : AfricaWork (BJ/TG/BF/ML/NE/GN/GA/CG/CD/KE), Novojob (BJ/TG), Minajobs, RMO, ANPEJ, Fonction Publique SN, concoursn, Sociumjob, Jooble, Talent.com, MyJobMag, Jobberman, Impactpool, UNjobs, AfDB, UNDP
- **P3 (~15)** : Jobartis, iWorks, DigiJob Guinée, Guineejob, MediaCongo, Radio Okapi, AfriqueJob, Afri-Emploi, JobAfrique, Michael Page, Talent2Africa, institutions régionales, Devex, Working Nomads
- **Exclu** : LinkedIn, Google Jobs (sans budget SerpAPI)

---

## Sources de la recherche

- [Emploi Dakar](https://www.emploidakar.com/) · [EmploiSenegal.com / AfricaWork](https://www.emploisenegal.com/) · [Senjob](https://senjob.com/sn/offres-d-emploi.php) · [Senego — sites recrutement Sénégal](https://senego.com/services/offres-emploi) · [Xarala — 5 plateformes emploi Sénégal](https://www.xarala.co/blog/5-plateformes-pour-trouver-un-emploi-rapidement-au-senegal-et-en-afrique/)
- [Socium — comparatif sites Afrique francophone 2026](https://sociumjob.com/medias/articles/meilleurs-sites-pour-postuler-en-afrique-francophone-le-comparatif-2026) · [Thot Cursus — répertoire sites emploi Afrique francophone](https://cursus.edu/fr/11623/repertoire-des-sites-doffres-demploi-maghreb-et-afrique-francophone) · [DigiJob Guinée — sites emploi Afrique de l'Ouest](https://digijobguinee.com/post.php?lang=fr&t=Les-Sites-D-offres-D-emploi-des-Pays-Francophones-En-Afrique-de-L-ouest&id=1122) · [ZeroName — top 10 plateformes emploi Afrique 2026](https://zeroname.space/ressources/top-10-plateformes-emploi-afrique)
- [Careerjet API (PublicAPIs.io)](https://publicapis.io/careerjet-api) · [Cavuno — job feeds 2026 (Jooble/Careerjet/Talent.com)](https://cavuno.com/blog/job-feeds) · [Apify — Africa Jobs Scraper (Jobberman/BrighterMonday/Careers24/MyJobMag)](https://apify.com/jungle_synthesizer/africa-jobs-aggregator-scraper) · [Kenyajob — Job API](https://www.kenyajob.com/job-api)
- [ReliefWeb — aide](https://reliefweb.int/help) · [ReliefWeb — flux RSS](https://reliefweb.int/rss) · [UN Talent — open project (API/RSS)](https://untalent.org/open) · [NGO Jobs in Africa](https://ngojobsinafrica.com/) · [Apify — Impactpool scraper](https://apify.com/nomad-agent/impactpool-scraper/api/python) · [The M&E Specialist — 15 best development job boards](https://themandespecialist.com/15-best-job-boards-international-development/)
- [Novojob West Africa (LinkedIn)](https://www.linkedin.com/company/novojobwa) · [Talent2Africa](https://talent2africa.com/) · [AfricaWork — emploi.cf](https://www.emploi.cf/) · [UNDP Jobs — région Afrique](https://jobs.undp.org/cj_view_jobs.cfm?cur_rgn_id_c=RAF)
