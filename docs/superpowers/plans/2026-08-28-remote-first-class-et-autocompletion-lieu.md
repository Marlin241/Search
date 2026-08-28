# Plan C — Remote premier plan + autocomplétion de localisation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire du remote une catégorie de premier plan (champ `is_remote` fiable sur chaque offre + badge « Remote » dans l'UI) et remplacer la saisie libre de localisation par une autocomplétion couvrant l'Afrique de l'Ouest/Centrale + la France.

**Architecture:** `JobListing` gagne `is_remote: bool`. Les sources 100 % remote (Jobicy, We Work Remotely) le posent à `True` ; `CrawledListingClient` le lit de sa colonne DB ; pour toutes les autres, l'agrégateur le dérive d'une heuristique texte partagée juste après le merge. `_passes_filters` et le scoring de compatibilité s'appuient sur ce champ au lieu de re-dériver l'heuristique chacun de leur côté. Côté frontend : un dataset statique `public/locations.json` (~300 villes) alimente le `TagInput` existant de l'onboarding (via sa prop `suggestions`) et un nouveau composant `LocationAutocomplete` mono-valeur pour le champ de recherche des offres.

**Tech Stack:** Backend : Python 3, FastAPI, Pydantic v2, pytest. Frontend : Next 16 (App Router, `next lint` / `next build` — **pas de framework de test unitaire**, vérification = build + lint + navigateur), React, Tailwind.

**Spec:** `docs/superpowers/specs/2026-08-28-sources-afrique-ouest-design.md` — composants 5, 6, 7.

## Global Constraints

- **Purement additif.** `is_remote` a une valeur par défaut (`False`) — aucun appelant existant de `JobListing(...)` ne casse.
- **Branche** `feature/talya-inspired-rebuild`, jamais `main`. Commits scopés (`git add <chemins>` explicites).
- **Backend** : `cd backend && ./venv/bin/python -m pytest` ; `./venv/bin/ruff check app/ tests/` ; `./venv/bin/ruff format` ; `./venv/bin/mypy app/`. Après modif backend testée en réel : `docker compose up -d --build backend` depuis la racine.
- **Frontend** : `cd frontend-v3 && npm run build && npm run lint`. `AGENTS.md` : lire `node_modules/next/dist/docs/` avant d'écrire du code Next si un doute sur une API. Le bloc « This is NOT the Next.js you know » réécrit par `next dev` dans `AGENTS.md` se committe avec le travail, ne pas le retirer du diff.
- **Vérif navigateur obligatoire** pour tout changement frontend non trivial (`claude-in-chrome`, port 3002) — cf. `[[dev-workflow-feedback]]`. Le dev server Turbopack est lent à hydrater : attendre 5-6 s après navigation avant le premier clic. La page `/offres` cache les résultats en `sessionStorage` 15 min — tester avec un mot-clé neuf ou vider le storage.
- **`JobListing.is_remote`** : nom exact, partout (schema, clients, agrégateur, `compatibility.py`, `types.ts`).
- **Format des villes** : nom nu (`"Dakar"`, `"Thiès"`, `"Abidjan"`, `"Paris"`), pas de suffixe pays — le backend fait du matching de sous-chaîne sur la localisation et `geo.api.gouv.fr` attend un nom de commune brut.

---

## File Structure

**Backend créés :**
- `backend/app/job_search/remote_signals.py` — `is_remote_from_text(*fragments: str | None) -> bool`, l'unique heuristique texte remote du projet.
- `backend/tests/job_search/test_remote_signals.py`

**Backend modifiés :**
- `backend/app/job_search/schemas.py` — `JobListing.is_remote: bool = False`.
- `backend/app/job_search/aggregator.py` — importe `is_remote_from_text` ; dans `search_jobs`, pose `listing.is_remote = listing.is_remote or is_remote_from_text(listing.location, listing.snippet)` avant `_passes_filters` ; `_passes_filters` teste `listing.is_remote` au lieu de `_matches_any(..., REMOTE_INDICATORS)`. `REMOTE_INDICATORS` et le `_matches_any` associé sont supprimés s'ils ne servent plus qu'à ça (garder `_matches_any` s'il sert encore aux `exclude_keywords` / contract types — il sert).
- `backend/app/job_search/jobicy.py` — `JobListing(..., is_remote=True)`.
- `backend/app/job_search/rss_feeds.py` — `is_remote=self._remote_only` dans le mapping (WWR/RemoteOK-like → True ; NGO Jobs → False, l'agrégateur complètera par heuristique).
- `backend/app/job_search/crawled_listings.py` — `JobListing(..., is_remote=row.is_remote)` (le champ existe déjà sur `CrawledListing`).
- `backend/app/job_search/compatibility.py` — `_score_location` utilise `listing.is_remote` ; `_REMOTE_INDICATORS` local supprimé.
- `backend/tests/job_search/test_aggregator.py`, `test_compatibility.py`, `test_jobicy.py`, `test_rss_feeds.py`, `test_crawled_listings_client.py` — assertions `is_remote`.

**Frontend créés :**
- `frontend-v3/public/locations.json` — `string[]` de ~300 villes (Afrique de l'Ouest/Centrale + France).
- `frontend-v3/lib/useCityList.ts` — hook, fetch `/locations.json` une fois, cache module-scope, renvoie `string[]` (`[]` tant que non chargé ou en cas d'échec).
- `frontend-v3/components/common/LocationAutocomplete.tsx` — champ mono-valeur contrôlé avec dropdown de suggestions.

**Frontend modifiés :**
- `frontend-v3/lib/types.ts` — `JobListing.is_remote: boolean`.
- `frontend-v3/lib/utils.ts` — `sourceLabel` : ajouter `reliefweb`, `jobicy`, `weworkremotely`, `ngojobs`, `emploi_dakar`, `crawled`.
- `frontend-v3/app/(app)/offres/page.tsx` — badge « 🌍 Remote » sur la carte quand `job.is_remote` ; remplacer le `<Input label="Localisation">` par `<LocationAutocomplete>`.
- `frontend-v3/components/onboarding/StepLocationAndContract.tsx` — passer `useCityList()` à `<TagInput suggestions={...}>` pour le champ Localisation.

---

## Task 1 : `remote_signals.py` + `JobListing.is_remote` + agrégateur + scoring

**Files:**
- Create: `backend/app/job_search/remote_signals.py`
- Create: `backend/tests/job_search/test_remote_signals.py`
- Modify: `backend/app/job_search/schemas.py`
- Modify: `backend/app/job_search/aggregator.py`
- Modify: `backend/app/job_search/compatibility.py`
- Modify: `backend/tests/job_search/test_aggregator.py`, `backend/tests/job_search/test_compatibility.py`

**Interfaces:**
- Produces : `is_remote_from_text(*fragments: str | None) -> bool` — `True` si l'un des fragments (concaténés, minuscule, accents retirés) contient `remote`, `teletravail`, `distanciel`, `hybride`, `télétravail`, `work from home`, `wfh`.
- Produces : `JobListing.is_remote: bool = False`.
- `search_jobs` renvoie des `JobListing` dont `is_remote` est renseigné pour **toutes** les offres (source-True OU heuristique).

- [ ] **Step 1: Écrire le test qui échoue (`remote_signals`)**

`backend/tests/job_search/test_remote_signals.py` :

```python
import pytest

from app.job_search.remote_signals import is_remote_from_text


@pytest.mark.parametrize(
    "fragments,expected",
    [
        (("Poste 100% télétravail",), True),
        (("Paris", "Full remote position"), True),
        ((None, "Travail à distance / distanciel"), True),
        (("Dakar, Sénégal", "Présentiel obligatoire"), False),
        ((None, None), False),
        (("Mode hybride 3j/semaine",), True),
        (("Work From Home",), True),
    ],
)
def test_is_remote_from_text(fragments, expected):
    assert is_remote_from_text(*fragments) is expected
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_remote_signals.py -q`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter `remote_signals.py`**

```python
import unicodedata

_MARKERS = (
    "remote",
    "teletravail",
    "distanciel",
    "hybride",
    "work from home",
    "wfh",
)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def is_remote_from_text(*fragments: str | None) -> bool:
    haystack = _normalize(" ".join(f for f in fragments if f))
    return any(marker in haystack for marker in _MARKERS)
```

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_remote_signals.py -q`
Expected: PASS (7 cas)

- [ ] **Step 5: Ajouter `is_remote` à `JobListing`**

Dans `backend/app/job_search/schemas.py`, classe `JobListing`, après `posted_at` :

```python
    is_remote: bool = False
```

- [ ] **Step 6: Agrégateur — poser `is_remote` et l'utiliser dans le filtre**

Dans `backend/app/job_search/aggregator.py` :

- Ajouter l'import : `from app.job_search.remote_signals import is_remote_from_text`
- Dans `_passes_filters`, remplacer la dernière expression :

```python
    return not (criteria.remote and not listing.is_remote)
```

- Dans `search_jobs`, dans la boucle de dédup, avant l'appel à `_passes_filters` :

```python
        listing.is_remote = listing.is_remote or is_remote_from_text(
            listing.location, listing.snippet
        )
```

- Supprimer la constante `REMOTE_INDICATORS` si elle n'est plus référencée (elle ne l'est plus). Garder `_matches_any` (encore utilisé pour `exclude_keywords` et les contract types).

- [ ] **Step 7: Mettre à jour les tests de l'agrégateur**

Dans `backend/tests/job_search/test_aggregator.py`, ajouter :

```python
def test_search_jobs_sets_is_remote_from_text_heuristic():
    remote_listing = _listing(
        title="Dev", snippet="Poste en télétravail total", url="https://x/r"
    )

    class C:
        def search(self, criteria):
            return [remote_listing]

    listings, _ = search_jobs(SearchCriteria(keywords="dev"), {"c": C()})
    assert listings[0].is_remote is True


def test_search_jobs_remote_filter_keeps_only_is_remote_listings():
    on_site = _listing(title="Dev", snippet="Présentiel", url="https://x/1")
    remote = _listing(title="Dev", snippet="Full remote", url="https://x/2")

    class C:
        def search(self, criteria):
            return [on_site, remote]

    listings, _ = search_jobs(
        SearchCriteria(keywords="dev", remote=True), {"c": C()}
    )
    assert [lst.url for lst in listings] == ["https://x/2"]
```

(Si un test existant `test_search_jobs...remote...` s'appuyait sur l'ancienne heuristique inline, l'adapter — le comportement observable est identique, seule la source du booléen change.)

- [ ] **Step 8: `compatibility.py` — utiliser `listing.is_remote`**

Dans `backend/app/job_search/compatibility.py`, `_score_location` :

```python
    is_remote_listing = listing.is_remote
```

(au lieu de `any(indicator in haystack for indicator in _REMOTE_INDICATORS)`). Le `haystack` reste utilisé pour le reste de la fonction s'il y sert encore ; sinon le retirer. Supprimer `_REMOTE_INDICATORS`.

Dans `backend/tests/job_search/test_compatibility.py` : les tests qui posent un listing « remote » via le texte du snippet continuent de marcher **uniquement si** le listing passe par l'agrégateur. Comme `score_listing`/`_score_location` sont souvent testés en isolation, **ces tests doivent maintenant poser `is_remote=True` explicitement sur le `JobListing` de test**. Parcourir `test_compatibility.py`, repérer les `JobListing(...)` avec un snippet type « télétravail » utilisés pour tester le score de localisation remote, et leur ajouter `is_remote=True`.

- [ ] **Step 9: Suite complète backend + lint + types**

Run: `cd backend && ./venv/bin/python -m pytest -q && ./venv/bin/ruff check app/ tests/ && ./venv/bin/ruff format --check app/ tests/ && ./venv/bin/mypy app/`
Expected: PASS (corriger les tests de compatibilité au besoin, cf. step 8).

- [ ] **Step 10: Commit**

```bash
git add backend/app/job_search/remote_signals.py backend/app/job_search/schemas.py backend/app/job_search/aggregator.py backend/app/job_search/compatibility.py backend/tests/job_search/test_remote_signals.py backend/tests/job_search/test_aggregator.py backend/tests/job_search/test_compatibility.py
git commit -m "feat(job-search): is_remote as a first-class JobListing field

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Task 2 : les sources posent `is_remote` à la source

**Files:**
- Modify: `backend/app/job_search/jobicy.py`
- Modify: `backend/app/job_search/rss_feeds.py`
- Modify: `backend/app/job_search/crawled_listings.py`
- Modify: `backend/tests/job_search/test_jobicy.py`, `test_rss_feeds.py`, `test_crawled_listings_client.py`

**Interfaces:**
- `JobicyClient` produit des `JobListing` avec `is_remote=True`.
- `RssFeedClient` produit `is_remote=self._remote_only`.
- `CrawledListingClient` produit `is_remote=row.is_remote`.

- [ ] **Step 1: Écrire/adapter les tests**

- `test_jobicy.py` : dans `test_search_returns_keyword_matched_listings`, ajouter `assert listings[0].is_remote is True`.
- `test_rss_feeds.py` : dans `test_returns_keyword_matched_entries_with_company_split` (client `remote_only=True`), ajouter `assert listings[0].is_remote is True` ; dans `test_non_remote_feed_returns_all_matches_when_no_location_pinned` (client `remote_only=False`), ajouter `assert all(lst.is_remote is False for lst in listings)`.
- `test_crawled_listings_client.py` : dans `test_search_remote_flag_restricts_to_remote_rows`, ajouter `assert results[0].is_remote is True` ; dans `test_search_matches_keyword_in_title`, `assert {r.is_remote for r in results} == {False, False}` n'a pas de sens — plutôt `assert next(r for r in results if r.url == "https://x/1").is_remote is False`.

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/test_jobicy.py tests/job_search/test_rss_feeds.py tests/job_search/test_crawled_listings_client.py -q`
Expected: FAIL sur les nouvelles assertions.

- [ ] **Step 3: Implémenter**

- `jobicy.py` : dans le `JobListing(...)`, ajouter `is_remote=True,`.
- `rss_feeds.py` : dans le `JobListing(...)`, ajouter `is_remote=self._remote_only,`.
- `crawled_listings.py` : dans le `JobListing(...)`, ajouter `is_remote=row.is_remote,`.

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `cd backend && ./venv/bin/python -m pytest tests/job_search/ -q`
Expected: PASS

- [ ] **Step 5: Lint / types / commit**

```bash
cd backend && ./venv/bin/ruff check app/ tests/ && ./venv/bin/ruff format --check app/ tests/ && ./venv/bin/mypy app/
git add backend/app/job_search/jobicy.py backend/app/job_search/rss_feeds.py backend/app/job_search/crawled_listings.py backend/tests/job_search/test_jobicy.py backend/tests/job_search/test_rss_feeds.py backend/tests/job_search/test_crawled_listings_client.py
git commit -m "feat(job-search): remote-only sources and crawled rows set is_remote at source

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Task 3 : Frontend — type `is_remote`, badge Remote, `sourceLabel`

**Files:**
- Modify: `frontend-v3/lib/types.ts`
- Modify: `frontend-v3/lib/utils.ts`
- Modify: `frontend-v3/app/(app)/offres/page.tsx`

**Interfaces:**
- `JobListing` (types.ts) gagne `is_remote: boolean;`.
- `sourceLabel` connaît les 6 nouvelles clés.
- La carte d'offre et la modale affichent un badge « 🌍 Remote » quand `job.is_remote`.

- [ ] **Step 1: `types.ts`**

Dans `interface JobListing`, après `compatibility_score: number;` :

```ts
  is_remote: boolean;
```

- [ ] **Step 2: `utils.ts` — `sourceLabel`**

Étendre la `map` :

```ts
    reliefweb: "ReliefWeb",
    jobicy: "Jobicy",
    weworkremotely: "We Work Remotely",
    ngojobs: "NGO Jobs in Africa",
    emploi_dakar: "Emploi Dakar",
    crawled: "Job board local",
```

- [ ] **Step 3: Badge Remote sur la carte**

Dans `frontend-v3/app/(app)/offres/page.tsx`, dans le bloc `{/* Meta badges */}` (vers la ligne 604, à côté de `<Badge variant="outline">{sourceLabel(job.source)}</Badge>`) :

```tsx
                        {job.is_remote && (
                          <Badge variant="accent">🌍 Remote</Badge>
                        )}
```

Et dans la modale de détail (vers la ligne 690, là où `sourceLabel(selectedModalJob.source)` est affiché), ajouter le même badge conditionné à `selectedModalJob.is_remote`.

- [ ] **Step 4: Build + lint**

Run: `cd frontend-v3 && npm run build && npm run lint`
Expected: build OK, aucune erreur de type (le `is_remote: boolean` non optionnel impose que toute construction de `JobListing` côté front le fournisse — vérifier qu'aucun mock/fixture front ne casse ; sinon le rendre optionnel `is_remote?: boolean` et tester `job.is_remote` en truthy).

- [ ] **Step 5: Vérif navigateur**

`claude-in-chrome`, http://localhost:3002/offres, recherche `developer` + case « Télétravail uniquement » → les cartes portent le badge « 🌍 Remote ». Recherche `comptable` + `Dakar` (mot-clé neuf pour éviter le cache) → offres `emploi_dakar` avec le label source « Emploi Dakar » lisible. Console sans erreur.

- [ ] **Step 6: Commit**

```bash
git add frontend-v3/lib/types.ts frontend-v3/lib/utils.ts "frontend-v3/app/(app)/offres/page.tsx"
git commit -m "feat(frontend-v3): Remote badge and labels for the new job sources

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Task 4 : Dataset de villes + composant `LocationAutocomplete`

**Files:**
- Create: `frontend-v3/public/locations.json`
- Create: `frontend-v3/lib/useCityList.ts`
- Create: `frontend-v3/components/common/LocationAutocomplete.tsx`

**Interfaces:**
- Produces : `useCityList(): string[]` — liste des villes, `[]` avant chargement / sur échec.
- Produces : `LocationAutocomplete` props : `{ value: string; onChange: (value: string) => void; label?: string; placeholder?: string; id?: string }`. Champ texte contrôlé + dropdown des 8 meilleures correspondances (préfixe puis sous-chaîne, insensible aux accents via la même `normalize` que `TagInput`). Sélectionner une suggestion appelle `onChange(city)` et ferme le dropdown. Frappe libre = `onChange(e.target.value)` (l'utilisateur peut taper une ville hors liste).

- [ ] **Step 1: `public/locations.json`**

Un tableau JSON de chaînes. Contenu (curated v1 — extensible plus tard) :

```json
["Dakar","Thiès","Touba","Rufisque","Saint-Louis","Kaolack","M'bour","Ziguinchor","Diourbel","Louga","Tambacounda","Richard-Toll","Kolda","Mbacké","Tivaouane","Joal-Fadiouth","Kaffrine","Matam","Fatick","Sédhiou","Kédougou","Abidjan","Bouaké","Daloa","Korhogo","San-Pédro","Yamoussoukro","Divo","Gagnoa","Man","Anyama","Abengourou","Grand-Bassam","Douala","Yaoundé","Garoua","Bafoussam","Bamenda","Maroua","Nkongsamba","Ngaoundéré","Bertoua","Édéa","Kribi","Buea","Limbé","Libreville","Port-Gentil","Franceville","Oyem","Moanda","Lambaréné","Cotonou","Porto-Novo","Parakou","Djougou","Bohicon","Abomey","Kandi","Lokossa","Ouidah","Natitingou","Lomé","Sokodé","Kara","Kpalimé","Atakpamé","Dapaong","Tsévié","Bamako","Sikasso","Koutiala","Ségou","Kayes","Mopti","Gao","Tombouctou","Ouagadougou","Bobo-Dioulasso","Koudougou","Banfora","Ouahigouya","Kaya","Brazzaville","Pointe-Noire","Dolisie","Nkayi","Owando","Conakry","Nzérékoré","Kankan","Kindia","Labé","Niamey","Zinder","Maradi","Agadez","Nouakchott","Nouadhibou","Bangui","N'Djaména","Kinshasa","Lubumbashi","Paris","Marseille","Lyon","Toulouse","Nice","Nantes","Montpellier","Strasbourg","Bordeaux","Lille","Rennes","Reims","Le Havre","Saint-Étienne","Toulon","Grenoble","Dijon","Angers","Nîmes","Villeurbanne","Clermont-Ferrand","Aix-en-Provence","Brest","Tours","Limoges","Amiens","Annecy","Perpignan","Metz","Besançon","Orléans","Rouen","Mulhouse","Caen","Nancy","Argenteuil","Montreuil","Roubaix","Tourcoing","Nanterre","Avignon","Poitiers","Créteil","Versailles","Pau","Courbevoie","Vitry-sur-Seine","Colombes","Aulnay-sous-Bois","La Rochelle","Rueil-Malmaison","Antibes","Cannes","Bruxelles","Genève","Lausanne","Luxembourg","Montréal","Casablanca","Rabat","Tunis","Alger","Remote","Télétravail"]
```

(« Remote » et « Télétravail » sont inclus comme choix explicites.)

- [ ] **Step 2: `lib/useCityList.ts`**

```ts
"use client";

import { useEffect, useState } from "react";

let cache: string[] | null = null;
let inFlight: Promise<string[]> | null = null;

async function load(): Promise<string[]> {
  if (cache) return cache;
  if (!inFlight) {
    inFlight = fetch("/locations.json")
      .then((r) => (r.ok ? r.json() : []))
      .then((data: unknown) => {
        cache = Array.isArray(data) ? (data as string[]) : [];
        return cache;
      })
      .catch(() => {
        cache = [];
        return cache;
      });
  }
  return inFlight;
}

export function useCityList(): string[] {
  const [cities, setCities] = useState<string[]>(cache ?? []);
  useEffect(() => {
    let alive = true;
    load().then((list) => {
      if (alive) setCities(list);
    });
    return () => {
      alive = false;
    };
  }, []);
  return cities;
}
```

- [ ] **Step 3: `components/common/LocationAutocomplete.tsx`**

Reprendre le style visuel de `Input` (`frontend-v3/components/ui/Input.tsx` — s'en inspirer pour les classes) et la logique de filtrage de `TagInput` (`normalize`, tri préfixe-d'abord).

```tsx
"use client";

import { useMemo, useState } from "react";
import { MapPin } from "lucide-react";
import { cn } from "@/lib/utils";
import { useCityList } from "@/lib/useCityList";

function normalize(value: string): string {
  return value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export interface LocationAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  placeholder?: string;
  id?: string;
}

export function LocationAutocomplete({
  value,
  onChange,
  label = "Localisation",
  placeholder = "ex : Dakar, Abidjan, Paris...",
  id,
}: LocationAutocompleteProps) {
  const cities = useCityList();
  const [open, setOpen] = useState(false);

  const suggestions = useMemo(() => {
    const q = normalize(value.trim());
    if (!q) return [];
    const scored = cities
      .filter((c) => normalize(c).includes(q))
      .sort((a, b) => {
        const as = normalize(a).startsWith(q) ? 0 : 1;
        const bs = normalize(b).startsWith(q) ? 0 : 1;
        return as - bs;
      })
      .slice(0, 8);
    return scored.length === 1 && normalize(scored[0]) === q ? [] : scored;
  }, [cities, value]);

  return (
    <div className="space-y-1.5">
      {label && (
        <label
          htmlFor={id}
          className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground"
        >
          {label}
        </label>
      )}
      <div className="relative">
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
          <MapPin className="h-4 w-4" />
        </span>
        <input
          id={id}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          placeholder={placeholder}
          className="w-full rounded-xl border border-input bg-card py-2.5 pl-9 pr-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground"
        />
        {open && suggestions.length > 0 && (
          <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-border bg-card shadow-lift">
            {suggestions.map((city) => (
              <button
                key={city}
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  onChange(city);
                  setOpen(false);
                }}
                className={cn(
                  "block w-full px-3 py-2 text-left text-sm text-foreground hover:bg-muted"
                )}
              >
                {city}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

> Vérifier les classes réelles contre `components/ui/Input.tsx` avant de figer (border radius, ring token) pour rester cohérent visuellement.

- [ ] **Step 4: Build + lint**

Run: `cd frontend-v3 && npm run build && npm run lint`
Expected: PASS. (Composant pas encore monté — juste compilé.)

- [ ] **Step 5: Commit**

```bash
git add frontend-v3/public/locations.json frontend-v3/lib/useCityList.ts frontend-v3/components/common/LocationAutocomplete.tsx
git commit -m "feat(frontend-v3): city dataset and LocationAutocomplete component

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Task 5 : Brancher l'autocomplétion (onboarding + recherche d'offres)

**Files:**
- Modify: `frontend-v3/components/onboarding/StepLocationAndContract.tsx`
- Modify: `frontend-v3/app/(app)/offres/page.tsx`

**Interfaces:**
- L'onboarding : le `TagInput` du champ Localisation reçoit `suggestions={useCityList()}`.
- La recherche d'offres : `<Input label="Localisation" ...>` remplacé par `<LocationAutocomplete value={location} onChange={setLocation} />`.

- [ ] **Step 1: Onboarding**

Dans `frontend-v3/components/onboarding/StepLocationAndContract.tsx` :
- Ajouter `import { useCityList } from "@/lib/useCityList";` et `const cities = useCityList();` dans le composant.
- Sur le `<TagInput label="Localisation" ...>`, ajouter `suggestions={cities}`.
- Mettre à jour le `placeholder` : `"ex : Dakar, Abidjan, Paris..."`.

- [ ] **Step 2: Recherche d'offres**

Dans `frontend-v3/app/(app)/offres/page.tsx` :
- `import { LocationAutocomplete } from "@/components/common/LocationAutocomplete";`
- Remplacer le bloc :
  ```tsx
  <Input
    label="Localisation"
    placeholder="ex: Paris, Lyon, Remote..."
    value={location}
    onChange={(e) => setLocation(e.target.value)}
    icon={<MapPin className="w-4 h-4" />}
  />
  ```
  par :
  ```tsx
  <LocationAutocomplete value={location} onChange={setLocation} />
  ```
- Si `MapPin` n'est plus utilisé ailleurs dans le fichier, retirer l'import (le lint le signalera).

- [ ] **Step 3: Build + lint**

Run: `cd frontend-v3 && npm run build && npm run lint`
Expected: PASS.

- [ ] **Step 4: Vérif navigateur (les deux points de montage)**

`claude-in-chrome`, port 3002 :
1. **Onboarding** (`/onboarding`, ou re-déclencher le wizard) : à l'étape localisation, taper `dak` → « Dakar » proposé, le sélectionner l'ajoute en tag. Taper `abi` → « Abidjan ».
2. **Recherche** (`/offres`) : cliquer le champ Localisation, taper `thi` → « Thiès » proposé ; le sélectionner remplit le champ ; lancer la recherche (`comptable` + `Thiès`) → la requête part avec `location=Thiès`. Taper une ville hors liste (`Kaolack` est dans la liste ; essayer `Bignona`) → la frappe libre reste possible, la recherche part quand même.
3. Console sans erreur ; `/locations.json` renvoie 200 (onglet réseau).

- [ ] **Step 5: Commit**

```bash
git add "frontend-v3/components/onboarding/StepLocationAndContract.tsx" "frontend-v3/app/(app)/offres/page.tsx"
git commit -m "feat(frontend-v3): wire LocationAutocomplete into onboarding and job search

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016jGYh2CXpyn3v3ezLcuLBa"
```

---

## Self-Review (effectué à la rédaction)

**Couverture du spec :**
- Composant 5 (`is_remote` sur `JobListing`, True d'office pour les sources remote, dérivé de l'heuristique pour les autres, badge Remote) → Tasks 1, 2, 3 ✅
- Composant 6 (remote comme mode : localisation optionnelle, offres `is_remote` non filtrées géographiquement) → Task 1 : `SearchCriteria.location` est déjà optionnel ; `_passes_filters` ne filtre pas par lieu ; le filtrage lieu se fait au niveau source, or une recherche `remote=True` sans lieu ne déclenche pas la suppression France-only du Plan B (qui ne s'active que si un lieu non-français est fourni). `_score_location` renvoie 100 pour une offre `is_remote` quand `remote_preference` est vrai (déjà le cas, désormais fiable). Rien de plus à coder — noté. ✅
- Composant 7 (`LocationAutocomplete`, dataset embarqué pays cibles + France, insensible aux accents, monté onboarding + recherche, dégradation gracieuse si le JSON ne charge pas) → Tasks 4, 5 ✅ (`useCityList` renvoie `[]` sur échec → `TagInput`/`LocationAutocomplete` fonctionnent en saisie libre).
- Hors scope confirmé : `remote_scope` (worldwide/region_locked), slider de salaire multi-devise, endpoint backend `/geo/locations` (fichier statique suffit). ✅

**Placeholders :** aucun TODO/TBD. `locations.json` est fourni en entier. Les numéros de ligne (`~604`, `~690`) sont des repères, le texte à chercher est cité.

**Cohérence des types :** `is_remote` — `bool = False` (schema) / `boolean` non optionnel (types.ts, avec repli optionnel documenté au step 3.4 si un mock front casse) / `row.is_remote` (colonne `CrawledListing`, existe depuis le Plan B) / `self._remote_only` (RssFeedClient, existe). `is_remote_from_text(*fragments: str | None) -> bool` — même signature step 3 (déf) / step 6 (appel agrégateur) / tests. `useCityList(): string[]` — même type consommé par `TagInput suggestions` (Task 5.1) et `LocationAutocomplete` (Task 4.3). `LocationAutocomplete` props `{value, onChange, label?, placeholder?, id?}` — mêmes au montage (Task 5.2).

**Dépendances inter-tâches :** Task 2 dépend de Task 1 (`is_remote` sur le schema). Task 3 dépend de Task 1 (champ dans la réponse API). Task 5 dépend de Task 4 (composant + hook). Ordre strict 1→2→3→4→5.

## Execution Handoff

Voir fin de conversation.
