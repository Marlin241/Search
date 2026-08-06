# Automatisation de candidature — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the frontend for sous-projet 2 per `docs/superpowers/specs/2026-08-06-automatisation-candidature-design.md`, consuming the API added by `docs/superpowers/plans/2026-08-06-automatisation-candidature-backend.md`: a `/profil` page to manage contact info and the reference CV, a `/candidatures` page to search offers, select them, review each diagnostic + CV/lettre + (for Greenhouse/Lever offers) a pre-filled application form, and confirm; and an `/historique` extension listing past applications.

**Architecture:** New `lib/api.ts`/`lib/types.ts` functions and types layered onto the existing ones (same `request`/`ApiError` helpers, same token-passed-explicitly convention). New presentational components follow the existing controlled-value pattern (`OfferInput`'s `{ value, onChange }` shape) for forms and the existing self-contained-async-state pattern (`PersonalizedDocumentCard`) for anything that calls the API directly. `DiagnosticReportView` and `PersonalizedDocumentCard` (sous-projets 1/3) are reused completely unchanged inside the new `ApplicationCard`.

**Tech Stack:** Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, vitest + @testing-library/react (existing stack, no new dependencies).

## Global Constraints

- All new API calls take `token: string` explicitly as their first argument and reuse the existing `request`/`requestBlob`/`ApiError` helpers in `lib/api.ts` — no new fetch wrapper.
- French UI copy throughout, matching the existing pages' tone (`app/diagnostic/page.tsx`, `app/historique/page.tsx`).
- No new dependencies: file upload reuses the existing `CVDropzone` component and `validateCvFile` helper; diagnostic display reuses `DiagnosticReportView`; CV/lettre generation reuses `PersonalizedDocumentCard` and the existing `generateCv`/`generateLetter`/`downloadCv`/`downloadLetter` functions — none of sous-projets 1/3's frontend code is modified.
- Selecting offers in search results is local component state only — nothing is sent to the backend until the user clicks the "lancer le diagnostic" action (matches the backend plan's assumption that no `Application` exists before that point).
- A custom field's `is_custom: true` in the pre-filled form review must be visibly flagged as LLM-generated and editable — never submitted as read-only text, per the spec's "always shown for review" requirement.
- Session-expiry handling (`isSessionExpired` + `logout()` + redirect to `/login`) follows the same pattern already used in `app/diagnostic/page.tsx` and `app/historique/page.tsx` on every new page.

---

### Task 1: `CandidateProfile` types and API client functions

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/api.test.ts`

**Interfaces:**
- Produces: `CandidateProfile` interface — `full_name: string`, `phone: string`, `address: string | null`, `linkedin_url: string | null`, `portfolio_url: string | null`, `work_authorization: string`, `salary_expectation: string | null`, `cv_filename: string | null`, `has_cv: boolean`, `updated_at: string`
- Produces: `CandidateProfileInput` interface — same fields as `CandidateProfile` minus `cv_filename`/`has_cv`/`updated_at`
- Produces: `getCandidateProfile(token: string): Promise<CandidateProfile>` (`GET /profile`)
- Produces: `updateCandidateProfile(token: string, payload: CandidateProfileInput): Promise<CandidateProfile>` (`PUT /profile`)
- Produces: `uploadReferenceCv(token: string, file: File): Promise<CandidateProfile>` (`POST /profile/cv`, multipart)

- [ ] **Step 1: Write the failing tests**

Append to `frontend/lib/api.test.ts` (reuses the file's existing `jsonResponse` helper and `beforeEach` fetch stub):
```typescript
import { getCandidateProfile, updateCandidateProfile, uploadReferenceCv } from "./api";

describe("getCandidateProfile", () => {
  it("gets /profile with the auth header", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        full_name: "Jane Doe",
        phone: "0612345678",
        address: null,
        linkedin_url: null,
        portfolio_url: null,
        work_authorization: "FR/UE",
        salary_expectation: null,
        cv_filename: null,
        has_cv: false,
        updated_at: "2026-08-06T00:00:00Z",
      })
    );
    const profile = await getCandidateProfile("tok");
    expect(profile.full_name).toBe("Jane Doe");

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/profile");
    expect((init?.headers as Headers).get("Authorization")).toBe("Bearer tok");
  });
});

describe("updateCandidateProfile", () => {
  it("puts JSON to /profile", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        full_name: "Jane Doe",
        phone: "0612345678",
        address: null,
        linkedin_url: null,
        portfolio_url: null,
        work_authorization: "FR/UE",
        salary_expectation: null,
        cv_filename: null,
        has_cv: false,
        updated_at: "2026-08-06T00:00:00Z",
      })
    );
    await updateCandidateProfile("tok", {
      full_name: "Jane Doe",
      phone: "0612345678",
      address: null,
      linkedin_url: null,
      portfolio_url: null,
      work_authorization: "FR/UE",
      salary_expectation: null,
    });

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/profile");
    expect(init?.method).toBe("PUT");
    expect(JSON.parse(init?.body as string).full_name).toBe("Jane Doe");
  });
});

describe("uploadReferenceCv", () => {
  it("posts the file as multipart form data to /profile/cv", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        full_name: "",
        phone: "",
        address: null,
        linkedin_url: null,
        portfolio_url: null,
        work_authorization: "",
        salary_expectation: null,
        cv_filename: "cv.pdf",
        has_cv: true,
        updated_at: "2026-08-06T00:00:00Z",
      })
    );
    const file = new File(["%PDF-1.4"], "cv.pdf", { type: "application/pdf" });

    const profile = await uploadReferenceCv("tok", file);

    expect(profile.has_cv).toBe(true);
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/profile/cv");
    expect(init?.body).toBeInstanceOf(FormData);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: FAIL — `getCandidateProfile is not a function` (or similar import error)

- [ ] **Step 3: Implement types and API functions**

Append to `frontend/lib/types.ts`:
```typescript
export interface CandidateProfile {
  full_name: string;
  phone: string;
  address: string | null;
  linkedin_url: string | null;
  portfolio_url: string | null;
  work_authorization: string;
  salary_expectation: string | null;
  cv_filename: string | null;
  has_cv: boolean;
  updated_at: string;
}

export interface CandidateProfileInput {
  full_name: string;
  phone: string;
  address: string | null;
  linkedin_url: string | null;
  portfolio_url: string | null;
  work_authorization: string;
  salary_expectation: string | null;
}
```

Append to `frontend/lib/api.ts` (add `CandidateProfile`, `CandidateProfileInput` to the existing `import type { ... } from "./types"` line):
```typescript
export function getCandidateProfile(token: string): Promise<CandidateProfile> {
  return request<CandidateProfile>("/profile", { method: "GET" }, token);
}

export function updateCandidateProfile(token: string, payload: CandidateProfileInput): Promise<CandidateProfile> {
  return request<CandidateProfile>(
    "/profile",
    { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) },
    token
  );
}

export function uploadReferenceCv(token: string, file: File): Promise<CandidateProfile> {
  const formData = new FormData();
  formData.append("cv_file", file);
  return request<CandidateProfile>("/profile/cv", { method: "POST", body: formData }, token);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts frontend/lib/api.test.ts
git commit -m "feat: add candidate profile API client"
```

---

### Task 2: `/profil` page

**Files:**
- Create: `frontend/components/CandidateProfileForm.tsx`
- Create: `frontend/components/CandidateProfileForm.test.tsx`
- Create: `frontend/app/profil/page.tsx`
- Modify: `frontend/components/TopNav.tsx`
- Modify: `frontend/components/TopNav.test.tsx`

**Interfaces:**
- Consumes: `CandidateProfile`, `CandidateProfileInput` (Task 1); `getCandidateProfile`, `updateCandidateProfile`, `uploadReferenceCv` (Task 1); `CVDropzone` (existing, `@/components/CVDropzone`); `RequireAuth` (existing); `ErrorBanner`, `toBannerContent`, `isSessionExpired` (existing)
- Produces: `CandidateProfileForm` component — controlled-value form (`{ value, onChange }`, matching `OfferInput`'s pattern) for the contact fields, plus an `onSubmit`/`isSubmitting` pair for the save action
- Produces: `CandidateProfileFormValue` type, `EMPTY_CANDIDATE_PROFILE_FORM_VALUE` constant, `toCandidateProfileInput(value: CandidateProfileFormValue): CandidateProfileInput` helper (empty strings become `null` for the optional fields, matching how the backend stores "not provided")

- [ ] **Step 1: Write the failing tests**

`frontend/components/CandidateProfileForm.test.tsx`:
```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { CandidateProfileForm, EMPTY_CANDIDATE_PROFILE_FORM_VALUE } from "./CandidateProfileForm";

describe("CandidateProfileForm", () => {
  it("renders the current value in each field", () => {
    render(
      <CandidateProfileForm
        value={{ ...EMPTY_CANDIDATE_PROFILE_FORM_VALUE, full_name: "Jane Doe" }}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        isSubmitting={false}
      />
    );
    expect(screen.getByLabelText(/nom complet/i)).toHaveValue("Jane Doe");
  });

  it("calls onChange when a field is edited", () => {
    const onChange = vi.fn();
    render(
      <CandidateProfileForm value={EMPTY_CANDIDATE_PROFILE_FORM_VALUE} onChange={onChange} onSubmit={vi.fn()} isSubmitting={false} />
    );
    fireEvent.change(screen.getByLabelText(/nom complet/i), { target: { value: "Jane Doe" } });
    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_CANDIDATE_PROFILE_FORM_VALUE, full_name: "Jane Doe" });
  });

  it("calls onSubmit when the save button is clicked", () => {
    const onSubmit = vi.fn();
    render(
      <CandidateProfileForm value={EMPTY_CANDIDATE_PROFILE_FORM_VALUE} onChange={vi.fn()} onSubmit={onSubmit} isSubmitting={false} />
    );
    fireEvent.click(screen.getByRole("button", { name: /enregistrer/i }));
    expect(onSubmit).toHaveBeenCalled();
  });

  it("disables the save button while submitting", () => {
    render(
      <CandidateProfileForm value={EMPTY_CANDIDATE_PROFILE_FORM_VALUE} onChange={vi.fn()} onSubmit={vi.fn()} isSubmitting={true} />
    );
    expect(screen.getByRole("button", { name: /enregistrement/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run components/CandidateProfileForm.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement the form component and the page**

`frontend/components/CandidateProfileForm.tsx`:
```typescript
"use client";

import type { CandidateProfileInput } from "@/lib/types";

export interface CandidateProfileFormValue {
  full_name: string;
  phone: string;
  address: string;
  linkedin_url: string;
  portfolio_url: string;
  work_authorization: string;
  salary_expectation: string;
}

export const EMPTY_CANDIDATE_PROFILE_FORM_VALUE: CandidateProfileFormValue = {
  full_name: "",
  phone: "",
  address: "",
  linkedin_url: "",
  portfolio_url: "",
  work_authorization: "",
  salary_expectation: "",
};

export function toCandidateProfileInput(value: CandidateProfileFormValue): CandidateProfileInput {
  return {
    full_name: value.full_name,
    phone: value.phone,
    address: value.address.trim() || null,
    linkedin_url: value.linkedin_url.trim() || null,
    portfolio_url: value.portfolio_url.trim() || null,
    work_authorization: value.work_authorization,
    salary_expectation: value.salary_expectation.trim() || null,
  };
}

interface CandidateProfileFormProps {
  value: CandidateProfileFormValue;
  onChange: (value: CandidateProfileFormValue) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
}

const FIELDS: Array<{ key: keyof CandidateProfileFormValue; label: string; required?: boolean }> = [
  { key: "full_name", label: "Nom complet", required: true },
  { key: "phone", label: "Téléphone", required: true },
  { key: "address", label: "Adresse" },
  { key: "linkedin_url", label: "URL LinkedIn" },
  { key: "portfolio_url", label: "URL portfolio" },
  { key: "work_authorization", label: "Autorisation de travail", required: true },
  { key: "salary_expectation", label: "Prétentions salariales" },
];

export function CandidateProfileForm({ value, onChange, onSubmit, isSubmitting }: CandidateProfileFormProps) {
  return (
    <div className="flex flex-col gap-4 rounded-xl bg-white p-4 shadow-sm">
      {FIELDS.map(({ key, label, required }) => (
        <label key={key} className="flex flex-col gap-1 text-sm text-slate-700">
          {label}
          <input
            type="text"
            value={value[key]}
            required={required}
            onChange={(event) => onChange({ ...value, [key]: event.target.value })}
            className="rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
      ))}
      <button
        type="button"
        onClick={onSubmit}
        disabled={isSubmitting}
        className="w-fit rounded-md bg-blue-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        {isSubmitting ? "Enregistrement..." : "Enregistrer"}
      </button>
    </div>
  );
}
```

`frontend/app/profil/page.tsx`:
```typescript
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import { CVDropzone } from "@/components/CVDropzone";
import { ErrorBanner } from "@/components/ErrorBanner";
import {
  CandidateProfileForm,
  EMPTY_CANDIDATE_PROFILE_FORM_VALUE,
  toCandidateProfileInput,
  type CandidateProfileFormValue,
} from "@/components/CandidateProfileForm";
import { toBannerContent, isSessionExpired, type BannerContent } from "@/lib/errors";
import { getCandidateProfile, updateCandidateProfile, uploadReferenceCv, ApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { CandidateProfile } from "@/lib/types";

export default function ProfilPage() {
  return (
    <RequireAuth>
      <ProfilPageContent />
    </RequireAuth>
  );
}

function ProfilPageContent() {
  const { token, logout } = useAuth();
  const router = useRouter();
  const [formValue, setFormValue] = useState<CandidateProfileFormValue>(EMPTY_CANDIDATE_PROFILE_FORM_VALUE);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [banner, setBanner] = useState<BannerContent | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isUploadingCv, setIsUploadingCv] = useState(false);

  function handleAuthError(error: unknown): boolean {
    if (isSessionExpired(error)) {
      logout();
      router.replace("/login");
      return true;
    }
    return false;
  }

  useEffect(() => {
    if (!token) return;
    getCandidateProfile(token)
      .then((fetched) => {
        setProfile(fetched);
        setFormValue({
          full_name: fetched.full_name,
          phone: fetched.phone,
          address: fetched.address ?? "",
          linkedin_url: fetched.linkedin_url ?? "",
          portfolio_url: fetched.portfolio_url ?? "",
          work_authorization: fetched.work_authorization,
          salary_expectation: fetched.salary_expectation ?? "",
        });
      })
      .catch((error) => {
        // 404 just means "no profile saved yet" — not an error to surface.
        if (error instanceof ApiError && error.status === 404) return;
        if (!handleAuthError(error)) setBanner(toBannerContent(error));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleSave() {
    if (!token) return;
    setBanner(null);
    setIsSaving(true);
    try {
      const updated = await updateCandidateProfile(token, toCandidateProfileInput(formValue));
      setProfile(updated);
    } catch (error) {
      if (!handleAuthError(error)) setBanner(toBannerContent(error));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleUploadCv() {
    if (!token || !cvFile) return;
    setBanner(null);
    setIsUploadingCv(true);
    try {
      const updated = await uploadReferenceCv(token, cvFile);
      setProfile(updated);
      setCvFile(null);
    } catch (error) {
      if (!handleAuthError(error)) setBanner(toBannerContent(error));
    } finally {
      setIsUploadingCv(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <h1 className="text-xl font-bold text-slate-900">Mon profil candidat</h1>
      <p className="mt-1 text-sm text-slate-600">
        Ces informations servent à pré-remplir vos candidatures automatiques.
      </p>

      {banner && (
        <div className="mt-4">
          <ErrorBanner content={banner} />
        </div>
      )}

      <div className="mt-6">
        <CandidateProfileForm value={formValue} onChange={setFormValue} onSubmit={handleSave} isSubmitting={isSaving} />
      </div>

      <div className="mt-6 rounded-xl bg-white p-4 shadow-sm">
        <p className="text-sm font-semibold text-slate-900">CV de référence</p>
        <p className="mt-1 text-sm text-slate-600">
          {profile?.has_cv ? `Fichier actuel : ${profile.cv_filename}` : "Aucun CV de référence uploadé pour le moment."}
        </p>
        <div className="mt-3 flex flex-col gap-3">
          <CVDropzone file={cvFile} onFileSelected={setCvFile} />
          <button
            type="button"
            onClick={handleUploadCv}
            disabled={!cvFile || isUploadingCv}
            className="w-fit rounded-md bg-blue-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {isUploadingCv ? "Envoi en cours..." : "Uploader mon CV de référence"}
          </button>
        </div>
      </div>
    </main>
  );
}
```

Modify `frontend/components/TopNav.tsx` — add two links inside the `<nav>`, right after the "Historique" link:
```typescript
<Link href="/candidatures" className={pathname === "/candidatures" ? "font-semibold text-blue-600" : ""}>
  Candidatures
</Link>
<Link href="/profil" className={pathname === "/profil" ? "font-semibold text-blue-600" : ""}>
  Profil
</Link>
```

Modify `frontend/components/TopNav.test.tsx` — extend the "shows nav links" assertion:
```typescript
    expect(screen.getByText("Historique")).toBeInTheDocument();
    expect(screen.getByText("Candidatures")).toBeInTheDocument();
    expect(screen.getByText("Profil")).toBeInTheDocument();
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run components/CandidateProfileForm.test.tsx components/TopNav.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/CandidateProfileForm.tsx frontend/components/CandidateProfileForm.test.tsx frontend/app/profil/page.tsx frontend/components/TopNav.tsx frontend/components/TopNav.test.tsx
git commit -m "feat: add candidate profile page"
```

---

### Task 3: `job_search` types and API client function

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/api.test.ts`

**Interfaces:**
- Produces: `SearchCriteria` interface — `keywords: string`, `location?: string`, `contract_type?: string`, `remote?: boolean`, `exclude_keywords: string[]`, `followed_companies: string[]`
- Produces: `JobListing` interface — `title: string`, `company: string`, `location: string | null`, `snippet: string`, `url: string`, `source: string`, `ats_type: string | null`
- Produces: `JobSearchResult` interface — `listings: JobListing[]`, `unavailable_sources: string[]`
- Produces: `searchJobs(token: string, criteria: SearchCriteria): Promise<JobSearchResult>` (`POST /job-search/search`)

- [ ] **Step 1: Write the failing test**

Append to `frontend/lib/api.test.ts`:
```typescript
import { searchJobs } from "./api";

describe("searchJobs", () => {
  it("posts criteria to /job-search/search and returns listings", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        listings: [
          {
            title: "Développeur Python",
            company: "Acme",
            location: "Paris",
            snippet: "...",
            url: "https://example.com/1",
            source: "adzuna",
            ats_type: null,
          },
        ],
        unavailable_sources: ["france_travail"],
      })
    );

    const result = await searchJobs("tok", {
      keywords: "python",
      exclude_keywords: [],
      followed_companies: [],
    });

    expect(result.listings).toHaveLength(1);
    expect(result.unavailable_sources).toEqual(["france_travail"]);
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/job-search/search");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string).keywords).toBe("python");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: FAIL — `searchJobs is not a function`

- [ ] **Step 3: Implement types and the API function**

Append to `frontend/lib/types.ts`:
```typescript
export interface SearchCriteria {
  keywords: string;
  location?: string;
  contract_type?: string;
  remote?: boolean;
  exclude_keywords: string[];
  followed_companies: string[];
}

export interface JobListing {
  title: string;
  company: string;
  location: string | null;
  snippet: string;
  url: string;
  source: string;
  ats_type: string | null;
}

export interface JobSearchResult {
  listings: JobListing[];
  unavailable_sources: string[];
}
```

Append to `frontend/lib/api.ts`:
```typescript
export function searchJobs(token: string, criteria: SearchCriteria): Promise<JobSearchResult> {
  return request<JobSearchResult>(
    "/job-search/search",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(criteria) },
    token
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts frontend/lib/api.test.ts
git commit -m "feat: add job search API client"
```

---

### Task 4: `SearchCriteriaForm` component

**Files:**
- Create: `frontend/components/SearchCriteriaForm.tsx`
- Create: `frontend/components/SearchCriteriaForm.test.tsx`

**Interfaces:**
- Consumes: `SearchCriteria` (Task 3)
- Produces: `SearchCriteriaFormValue` type (all fields as plain strings/booleans for controlled inputs — `excludeKeywords`/`followedCompanies` are raw comma-separated text, split into arrays only at submit time), `EMPTY_SEARCH_CRITERIA_FORM_VALUE` constant, `toSearchCriteria(value: SearchCriteriaFormValue): SearchCriteria` helper
- Produces: `SearchCriteriaForm` component — controlled-value form (`{ value, onChange }`, matching `OfferInput`) plus `onSearch`/`isSearching`

- [ ] **Step 1: Write the failing tests**

`frontend/components/SearchCriteriaForm.test.tsx`:
```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import {
  SearchCriteriaForm,
  EMPTY_SEARCH_CRITERIA_FORM_VALUE,
  toSearchCriteria,
} from "./SearchCriteriaForm";

describe("SearchCriteriaForm", () => {
  it("calls onChange when the keywords field is edited", () => {
    const onChange = vi.fn();
    render(
      <SearchCriteriaForm value={EMPTY_SEARCH_CRITERIA_FORM_VALUE} onChange={onChange} onSearch={vi.fn()} isSearching={false} />
    );
    fireEvent.change(screen.getByLabelText(/mots-clés/i), { target: { value: "python" } });
    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_SEARCH_CRITERIA_FORM_VALUE, keywords: "python" });
  });

  it("calls onSearch when the search button is clicked", () => {
    const onSearch = vi.fn();
    render(
      <SearchCriteriaForm value={EMPTY_SEARCH_CRITERIA_FORM_VALUE} onChange={vi.fn()} onSearch={onSearch} isSearching={false} />
    );
    fireEvent.click(screen.getByRole("button", { name: /rechercher/i }));
    expect(onSearch).toHaveBeenCalled();
  });

  it("disables the search button while searching", () => {
    render(
      <SearchCriteriaForm value={EMPTY_SEARCH_CRITERIA_FORM_VALUE} onChange={vi.fn()} onSearch={vi.fn()} isSearching={true} />
    );
    expect(screen.getByRole("button", { name: /recherche en cours/i })).toBeDisabled();
  });
});

describe("toSearchCriteria", () => {
  it("splits comma-separated fields into trimmed arrays", () => {
    const result = toSearchCriteria({
      ...EMPTY_SEARCH_CRITERIA_FORM_VALUE,
      keywords: "python",
      excludeKeywords: "stage, junior",
      followedCompanies: "acme, globex",
    });
    expect(result.exclude_keywords).toEqual(["stage", "junior"]);
    expect(result.followed_companies).toEqual(["acme", "globex"]);
  });

  it("omits empty optional fields", () => {
    const result = toSearchCriteria(EMPTY_SEARCH_CRITERIA_FORM_VALUE);
    expect(result.location).toBeUndefined();
    expect(result.contract_type).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run components/SearchCriteriaForm.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement the component**

`frontend/components/SearchCriteriaForm.tsx`:
```typescript
"use client";

import type { SearchCriteria } from "@/lib/types";

export interface SearchCriteriaFormValue {
  keywords: string;
  location: string;
  contractType: string;
  remote: boolean;
  excludeKeywords: string;
  followedCompanies: string;
}

export const EMPTY_SEARCH_CRITERIA_FORM_VALUE: SearchCriteriaFormValue = {
  keywords: "",
  location: "",
  contractType: "",
  remote: false,
  excludeKeywords: "",
  followedCompanies: "",
};

function splitCommaList(raw: string): string[] {
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

export function toSearchCriteria(value: SearchCriteriaFormValue): SearchCriteria {
  return {
    keywords: value.keywords,
    location: value.location.trim() || undefined,
    contract_type: value.contractType.trim() || undefined,
    remote: value.remote || undefined,
    exclude_keywords: splitCommaList(value.excludeKeywords),
    followed_companies: splitCommaList(value.followedCompanies),
  };
}

interface SearchCriteriaFormProps {
  value: SearchCriteriaFormValue;
  onChange: (value: SearchCriteriaFormValue) => void;
  onSearch: () => void;
  isSearching: boolean;
}

export function SearchCriteriaForm({ value, onChange, onSearch, isSearching }: SearchCriteriaFormProps) {
  return (
    <div className="flex flex-col gap-4 rounded-xl bg-white p-4 shadow-sm">
      <label className="flex flex-col gap-1 text-sm text-slate-700">
        Mots-clés
        <input
          type="text"
          value={value.keywords}
          onChange={(event) => onChange({ ...value, keywords: event.target.value })}
          placeholder="ex: développeur python"
          className="rounded-md border border-slate-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-700">
        Localisation
        <input
          type="text"
          value={value.location}
          onChange={(event) => onChange({ ...value, location: event.target.value })}
          className="rounded-md border border-slate-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-700">
        Type de contrat
        <input
          type="text"
          value={value.contractType}
          onChange={(event) => onChange({ ...value, contractType: event.target.value })}
          placeholder="ex: CDI"
          className="rounded-md border border-slate-300 px-3 py-2"
        />
      </label>
      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={value.remote}
          onChange={(event) => onChange({ ...value, remote: event.target.checked })}
        />
        Télétravail uniquement
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-700">
        Mots-clés à exclure (séparés par des virgules)
        <input
          type="text"
          value={value.excludeKeywords}
          onChange={(event) => onChange({ ...value, excludeKeywords: event.target.value })}
          className="rounded-md border border-slate-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-700">
        Entreprises à suivre sur Greenhouse/Lever (séparées par des virgules)
        <input
          type="text"
          value={value.followedCompanies}
          onChange={(event) => onChange({ ...value, followedCompanies: event.target.value })}
          placeholder="ex: acme, globex"
          className="rounded-md border border-slate-300 px-3 py-2"
        />
      </label>
      <button
        type="button"
        onClick={onSearch}
        disabled={isSearching || value.keywords.trim().length === 0}
        className="w-fit rounded-md bg-blue-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        {isSearching ? "Recherche en cours..." : "Rechercher"}
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run components/SearchCriteriaForm.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/SearchCriteriaForm.tsx frontend/components/SearchCriteriaForm.test.tsx
git commit -m "feat: add search criteria form"
```

---

### Task 5: `Application`/`FormField` types and API client functions

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/api.test.ts`

**Interfaces:**
- Consumes: `DiagnosticReport` (existing, `lib/types.ts`)
- Produces: `Application` interface — `id: number`, `diagnostic_id: number`, `offer_url: string`, `source: string`, `company_name: string`, `job_title: string`, `ats_type: string | null`, `status: "en_cours" | "soumise_auto" | "a_soumettre_manuellement" | "soumise_manuelle_confirmee" | "echec_soumission"`, `error_message: string | null`, `submitted_at: string | null`, `created_at: string`, `updated_at: string`, `diagnostic: DiagnosticReport`
- Produces: `ApplicationCreateInput` interface — `offer_url: string`, `offer_text?: string`, `source: string`, `company_name: string`, `job_title: string`, `ats_type?: string | null`
- Produces: `FormField` interface — `name: string`, `label: string`, `field_type: string`, `required: boolean`, `options: string[] | null`, `value: string | null`, `is_custom: boolean`
- Produces: `PrefilledForm` interface — `fields: FormField[]`
- Produces: `createApplication(token: string, payload: ApplicationCreateInput): Promise<Application>` (`POST /applications`), `listApplications(token: string): Promise<Application[]>` (`GET /applications`), `getApplication(token: string, id: number): Promise<Application>` (`GET /applications/{id}`), `getPrefilledForm(token: string, applicationId: number): Promise<PrefilledForm>` (`GET /applications/{id}/prefilled-form`), `confirmApplication(token: string, applicationId: number, fields?: FormField[]): Promise<Application>` (`POST /applications/{id}/confirm`), `markApplicationSentManually(token: string, applicationId: number): Promise<Application>` (`POST /applications/{id}/mark-sent`)

- [ ] **Step 1: Write the failing tests**

Append to `frontend/lib/api.test.ts`:
```typescript
import {
  createApplication,
  listApplications,
  getApplication,
  getPrefilledForm,
  confirmApplication,
  markApplicationSentManually,
} from "./api";

const sampleDiagnostic = {
  id: 1,
  created_at: "2026-08-06T00:00:00Z",
  overall_score: 70,
  structural_score: 80,
  structural_issues: [],
  semantic_score: 60,
  missing_keywords: ["Docker"],
  recommendations: ["Add Docker"],
};

const sampleApplication = {
  id: 1,
  diagnostic_id: 1,
  offer_url: "https://example.com/job/1",
  source: "manual",
  company_name: "Acme",
  job_title: "Développeur",
  ats_type: null,
  status: "en_cours",
  error_message: null,
  submitted_at: null,
  created_at: "2026-08-06T00:00:00Z",
  updated_at: "2026-08-06T00:00:00Z",
  diagnostic: sampleDiagnostic,
};

describe("createApplication", () => {
  it("posts JSON to /applications", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(sampleApplication, 201));
    const application = await createApplication("tok", {
      offer_url: "https://example.com/job/1",
      offer_text: "Offre.",
      source: "manual",
      company_name: "Acme",
      job_title: "Développeur",
    });
    expect(application.status).toBe("en_cours");
    expect(application.diagnostic.missing_keywords).toEqual(["Docker"]);
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/applications");
    expect(init?.method).toBe("POST");
  });
});

describe("listApplications", () => {
  it("gets /applications", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse([sampleApplication]));
    const applications = await listApplications("tok");
    expect(applications).toHaveLength(1);
  });
});

describe("getApplication", () => {
  it("gets /applications/:id", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(sampleApplication));
    const application = await getApplication("tok", 1);
    expect(application.id).toBe(1);
    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/applications/1");
  });
});

describe("getPrefilledForm", () => {
  it("gets /applications/:id/prefilled-form", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        fields: [
          { name: "first_name", label: "First name", field_type: "text", required: true, options: null, value: "Jane", is_custom: false },
        ],
      })
    );
    const form = await getPrefilledForm("tok", 1);
    expect(form.fields[0].value).toBe("Jane");
    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/applications/1/prefilled-form");
  });
});

describe("confirmApplication", () => {
  it("posts fields (or null) to /applications/:id/confirm", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ ...sampleApplication, status: "soumise_auto" }));
    const application = await confirmApplication("tok", 1, [
      { name: "first_name", label: "First name", field_type: "text", required: true, options: null, value: "Jane", is_custom: false },
    ]);
    expect(application.status).toBe("soumise_auto");
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/applications/1/confirm");
    expect(JSON.parse(init?.body as string).fields[0].name).toBe("first_name");
  });

  it("sends null fields when called without any (assisted mode)", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ ...sampleApplication, status: "a_soumettre_manuellement" }));
    await confirmApplication("tok", 1);
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(JSON.parse(init?.body as string).fields).toBeNull();
  });
});

describe("markApplicationSentManually", () => {
  it("posts to /applications/:id/mark-sent", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ ...sampleApplication, status: "soumise_manuelle_confirmee" }));
    const application = await markApplicationSentManually("tok", 1);
    expect(application.status).toBe("soumise_manuelle_confirmee");
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/applications/1/mark-sent");
    expect(init?.method).toBe("POST");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: FAIL — `createApplication is not a function`

- [ ] **Step 3: Implement types and API functions**

Append to `frontend/lib/types.ts`:
```typescript
export interface Application {
  id: number;
  diagnostic_id: number;
  offer_url: string;
  source: string;
  company_name: string;
  job_title: string;
  ats_type: string | null;
  status: "en_cours" | "soumise_auto" | "a_soumettre_manuellement" | "soumise_manuelle_confirmee" | "echec_soumission";
  error_message: string | null;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
  diagnostic: DiagnosticReport;
}

export interface ApplicationCreateInput {
  offer_url: string;
  offer_text?: string;
  source: string;
  company_name: string;
  job_title: string;
  ats_type?: string | null;
}

export interface FormField {
  name: string;
  label: string;
  field_type: string;
  required: boolean;
  options: string[] | null;
  value: string | null;
  is_custom: boolean;
}

export interface PrefilledForm {
  fields: FormField[];
}
```

Append to `frontend/lib/api.ts`:
```typescript
export function createApplication(token: string, payload: ApplicationCreateInput): Promise<Application> {
  return request<Application>(
    "/applications",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) },
    token
  );
}

export function listApplications(token: string): Promise<Application[]> {
  return request<Application[]>("/applications", { method: "GET" }, token);
}

export function getApplication(token: string, id: number): Promise<Application> {
  return request<Application>(`/applications/${id}`, { method: "GET" }, token);
}

export function getPrefilledForm(token: string, applicationId: number): Promise<PrefilledForm> {
  return request<PrefilledForm>(`/applications/${applicationId}/prefilled-form`, { method: "GET" }, token);
}

export function confirmApplication(token: string, applicationId: number, fields?: FormField[]): Promise<Application> {
  return request<Application>(
    `/applications/${applicationId}/confirm`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fields: fields ?? null }) },
    token
  );
}

export function markApplicationSentManually(token: string, applicationId: number): Promise<Application> {
  return request<Application>(`/applications/${applicationId}/mark-sent`, { method: "POST" }, token);
}
```

(Add `Application`, `ApplicationCreateInput`, `FormField`, `PrefilledForm` to the existing `import type { ... } from "./types"` line at the top of `frontend/lib/api.ts`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts frontend/lib/api.test.ts
git commit -m "feat: add applications API client"
```

---

### Task 6: `PrefilledFormReview` component

**Files:**
- Create: `frontend/components/PrefilledFormReview.tsx`
- Create: `frontend/components/PrefilledFormReview.test.tsx`

**Interfaces:**
- Consumes: `FormField` (Task 5)
- Produces: `PrefilledFormReview` component — `fields: FormField[]`, `onConfirm: (fields: FormField[]) => void`, `onCancel: () => void`, `isConfirming: boolean`

Every field is rendered as an editable input regardless of `is_custom` — a custom (LLM-answered) field gets an additional "généré par l'IA" hint, but the user can edit any field, standard or custom, before confirming. This is the "always shown for review" requirement from the spec, not an optional nicety.

- [ ] **Step 1: Write the failing tests**

`frontend/components/PrefilledFormReview.test.tsx`:
```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { PrefilledFormReview } from "./PrefilledFormReview";
import type { FormField } from "@/lib/types";

const fields: FormField[] = [
  { name: "first_name", label: "First name", field_type: "text", required: true, options: null, value: "Jane", is_custom: false },
  { name: "custom_why", label: "Why this role?", field_type: "textarea", required: false, options: null, value: "Réponse générée.", is_custom: true },
];

describe("PrefilledFormReview", () => {
  it("renders each field's current value", () => {
    render(<PrefilledFormReview fields={fields} onConfirm={vi.fn()} onCancel={vi.fn()} isConfirming={false} />);
    expect(screen.getByLabelText(/first name/i)).toHaveValue("Jane");
    expect(screen.getByLabelText(/why this role/i)).toHaveValue("Réponse générée.");
  });

  it("flags custom fields as LLM-generated", () => {
    render(<PrefilledFormReview fields={fields} onConfirm={vi.fn()} onCancel={vi.fn()} isConfirming={false} />);
    expect(screen.getByText(/généré par l'ia/i)).toBeInTheDocument();
  });

  it("lets the user edit a field before confirming", () => {
    const onConfirm = vi.fn();
    render(<PrefilledFormReview fields={fields} onConfirm={onConfirm} onCancel={vi.fn()} isConfirming={false} />);

    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: "Janet" } });
    fireEvent.click(screen.getByRole("button", { name: /envoyer la candidature/i }));

    expect(onConfirm).toHaveBeenCalledWith([
      { ...fields[0], value: "Janet" },
      fields[1],
    ]);
  });

  it("calls onCancel when cancel is clicked", () => {
    const onCancel = vi.fn();
    render(<PrefilledFormReview fields={fields} onConfirm={vi.fn()} onCancel={onCancel} isConfirming={false} />);
    fireEvent.click(screen.getByRole("button", { name: /annuler/i }));
    expect(onCancel).toHaveBeenCalled();
  });

  it("disables the confirm button while confirming", () => {
    render(<PrefilledFormReview fields={fields} onConfirm={vi.fn()} onCancel={vi.fn()} isConfirming={true} />);
    expect(screen.getByRole("button", { name: /envoi en cours/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run components/PrefilledFormReview.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement the component**

`frontend/components/PrefilledFormReview.tsx`:
```typescript
"use client";

import { useState } from "react";
import type { FormField } from "@/lib/types";

interface PrefilledFormReviewProps {
  fields: FormField[];
  onConfirm: (fields: FormField[]) => void;
  onCancel: () => void;
  isConfirming: boolean;
}

export function PrefilledFormReview({ fields, onConfirm, onCancel, isConfirming }: PrefilledFormReviewProps) {
  const [values, setValues] = useState<FormField[]>(fields);

  function updateValue(name: string, newValue: string) {
    setValues((prev) => prev.map((field) => (field.name === name ? { ...field, value: newValue } : field)));
  }

  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
      <p className="text-sm font-semibold text-slate-900">Relisez et complétez le formulaire avant l&apos;envoi</p>
      <div className="mt-3 flex flex-col gap-3">
        {values.map((field) => (
          <label key={field.name} className="flex flex-col gap-1 text-sm text-slate-700">
            <span>
              {field.label}
              {field.is_custom && <span className="ml-2 text-xs text-blue-600">(généré par l&apos;IA — à vérifier)</span>}
            </span>
            {field.field_type === "textarea" ? (
              <textarea
                value={field.value ?? ""}
                onChange={(event) => updateValue(field.name, event.target.value)}
                rows={3}
                className="rounded-md border border-slate-300 px-3 py-2"
              />
            ) : (
              <input
                type="text"
                value={field.value ?? ""}
                onChange={(event) => updateValue(field.name, event.target.value)}
                className="rounded-md border border-slate-300 px-3 py-2"
              />
            )}
          </label>
        ))}
      </div>
      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={() => onConfirm(values)}
          disabled={isConfirming}
          className="rounded-md bg-blue-500 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {isConfirming ? "Envoi en cours..." : "Envoyer la candidature"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
        >
          Annuler
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run components/PrefilledFormReview.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/PrefilledFormReview.tsx frontend/components/PrefilledFormReview.test.tsx
git commit -m "feat: add prefilled application form review component"
```

---

### Task 7: `ApplicationCard` component

**Files:**
- Create: `frontend/components/ApplicationCard.tsx`
- Create: `frontend/components/ApplicationCard.test.tsx`

**Interfaces:**
- Consumes: `Application`, `FormField` (Task 5); `PrefilledFormReview` (Task 6); `generateCv`, `generateLetter`, `downloadCv`, `downloadLetter`, `getPrefilledForm`, `confirmApplication`, `markApplicationSentManually` (existing + Task 5, `@/lib/api`); `DiagnosticReportView`, `PersonalizedDocumentCard`, `ErrorBanner` (existing components); `toBannerContent` (existing, `@/lib/errors`)
- Produces: `ApplicationCard` component — `application: Application`, `token: string`, `onUpdated: (updated: Application) => void`

Owns its own async state end-to-end (matches `PersonalizedDocumentCard`'s self-contained pattern) rather than taking callback props for every action — the parent (`/candidatures` page, Task 9) only needs to know when an `Application` changed, via `onUpdated`.

Behavior by `ats_type`/`status`:
- `ats_type` set and `status === "en_cours"`: "Confirmer la candidature" button fetches the pre-filled form and renders `PrefilledFormReview`; confirming it calls `confirmApplication` with the (possibly edited) fields.
- `ats_type === null` and `status === "en_cours"`: "Confirmer la candidature" calls `confirmApplication` directly with no fields — nothing to review, since there is no form to pre-fill; this transitions the application to `a_soumettre_manuellement`.
- `status === "a_soumettre_manuellement"`: shows a link to the offer plus a "Marquer comme envoyée" button.
- Any other status: read-only, just shows the status badge (and `error_message` if `echec_soumission`).

- [ ] **Step 1: Write the failing tests**

`frontend/components/ApplicationCard.test.tsx`:
```typescript
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApplicationCard } from "./ApplicationCard";
import * as api from "@/lib/api";
import type { Application } from "@/lib/types";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    generateCv: vi.fn(),
    generateLetter: vi.fn(),
    downloadCv: vi.fn(),
    downloadLetter: vi.fn(),
    getPrefilledForm: vi.fn(),
    confirmApplication: vi.fn(),
    markApplicationSentManually: vi.fn(),
    ApiError: actual.ApiError,
  };
});

const diagnostic = {
  id: 1,
  created_at: "2026-08-06T00:00:00Z",
  overall_score: 70,
  structural_score: 80,
  structural_issues: [],
  semantic_score: 60,
  missing_keywords: ["Docker"],
  recommendations: ["Add Docker"],
};

function makeApplication(overrides: Partial<Application> = {}): Application {
  return {
    id: 1,
    diagnostic_id: 1,
    offer_url: "https://example.com/job/1",
    source: "manual",
    company_name: "Acme",
    job_title: "Développeur Python",
    ats_type: null,
    status: "en_cours",
    error_message: null,
    submitted_at: null,
    created_at: "2026-08-06T00:00:00Z",
    updated_at: "2026-08-06T00:00:00Z",
    diagnostic,
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(api.generateCv).mockReset();
  vi.mocked(api.getPrefilledForm).mockReset();
  vi.mocked(api.confirmApplication).mockReset();
  vi.mocked(api.markApplicationSentManually).mockReset();
});

describe("ApplicationCard", () => {
  it("renders the offer title, company, and diagnostic report", () => {
    render(<ApplicationCard application={makeApplication()} token="tok" onUpdated={vi.fn()} />);
    expect(screen.getByText("Développeur Python")).toBeInTheDocument();
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByText(/docker/i)).toBeInTheDocument();
  });

  it("confirms directly (no review step) for a non-ATS offer", async () => {
    const onUpdated = vi.fn();
    vi.mocked(api.confirmApplication).mockResolvedValue(
      makeApplication({ status: "a_soumettre_manuellement" })
    );
    render(<ApplicationCard application={makeApplication()} token="tok" onUpdated={onUpdated} />);

    fireEvent.click(screen.getByRole("button", { name: /confirmer la candidature/i }));

    await waitFor(() => expect(api.confirmApplication).toHaveBeenCalledWith("tok", 1));
    expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ status: "a_soumettre_manuellement" }));
  });

  it("fetches and shows the prefilled form review for an ATS-eligible offer", async () => {
    vi.mocked(api.getPrefilledForm).mockResolvedValue({
      fields: [
        { name: "first_name", label: "First name", field_type: "text", required: true, options: null, value: "Jane", is_custom: false },
      ],
    });
    render(
      <ApplicationCard application={makeApplication({ ats_type: "greenhouse" })} token="tok" onUpdated={vi.fn()} />
    );

    fireEvent.click(screen.getByRole("button", { name: /confirmer la candidature/i }));

    expect(await screen.findByLabelText(/first name/i)).toHaveValue("Jane");
    expect(api.getPrefilledForm).toHaveBeenCalledWith("tok", 1);
  });

  it("submits the edited fields from the review step", async () => {
    vi.mocked(api.getPrefilledForm).mockResolvedValue({
      fields: [
        { name: "first_name", label: "First name", field_type: "text", required: true, options: null, value: "Jane", is_custom: false },
      ],
    });
    vi.mocked(api.confirmApplication).mockResolvedValue(makeApplication({ ats_type: "greenhouse", status: "soumise_auto" }));
    const onUpdated = vi.fn();
    render(
      <ApplicationCard application={makeApplication({ ats_type: "greenhouse" })} token="tok" onUpdated={onUpdated} />
    );
    fireEvent.click(screen.getByRole("button", { name: /confirmer la candidature/i }));
    await screen.findByLabelText(/first name/i);

    fireEvent.click(screen.getByRole("button", { name: /envoyer la candidature/i }));

    await waitFor(() =>
      expect(api.confirmApplication).toHaveBeenCalledWith(
        "tok",
        1,
        expect.arrayContaining([expect.objectContaining({ name: "first_name", value: "Jane" })])
      )
    );
    expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ status: "soumise_auto" }));
  });

  it("shows the offer link and a mark-sent button in assisted mode", async () => {
    const onUpdated = vi.fn();
    vi.mocked(api.markApplicationSentManually).mockResolvedValue(
      makeApplication({ status: "soumise_manuelle_confirmee" })
    );
    render(
      <ApplicationCard application={makeApplication({ status: "a_soumettre_manuellement" })} token="tok" onUpdated={onUpdated} />
    );

    expect(screen.getByRole("link", { name: /ouvrir la page de candidature/i })).toHaveAttribute(
      "href",
      "https://example.com/job/1"
    );

    fireEvent.click(screen.getByRole("button", { name: /marquer comme envoyée/i }));

    await waitFor(() => expect(api.markApplicationSentManually).toHaveBeenCalledWith("tok", 1));
    expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ status: "soumise_manuelle_confirmee" }));
  });

  it("shows the error message for a failed submission", () => {
    render(
      <ApplicationCard
        application={makeApplication({ status: "echec_soumission", error_message: "Le serveur a refusé la soumission." })}
        token="tok"
        onUpdated={vi.fn()}
      />
    );
    expect(screen.getByText("Le serveur a refusé la soumission.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run components/ApplicationCard.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement the component**

`frontend/components/ApplicationCard.tsx`:
```typescript
"use client";

import { useState } from "react";
import { DiagnosticReportView } from "./DiagnosticReportView";
import { PersonalizedDocumentCard } from "./PersonalizedDocumentCard";
import { PrefilledFormReview } from "./PrefilledFormReview";
import { ErrorBanner } from "./ErrorBanner";
import { toBannerContent, type BannerContent } from "@/lib/errors";
import {
  generateCv,
  generateLetter,
  downloadCv,
  downloadLetter,
  getPrefilledForm,
  confirmApplication,
  markApplicationSentManually,
} from "@/lib/api";
import type { Application, FormField } from "@/lib/types";

interface ApplicationCardProps {
  application: Application;
  token: string;
  onUpdated: (updated: Application) => void;
}

const STATUS_LABELS: Record<Application["status"], string> = {
  en_cours: "En attente de confirmation",
  soumise_auto: "Candidature envoyée automatiquement",
  a_soumettre_manuellement: "À envoyer manuellement",
  soumise_manuelle_confirmee: "Envoyée",
  echec_soumission: "Échec de l'envoi",
};

export function ApplicationCard({ application, token, onUpdated }: ApplicationCardProps) {
  const [banner, setBanner] = useState<BannerContent | null>(null);
  const [isLoadingForm, setIsLoadingForm] = useState(false);
  const [prefilledFields, setPrefilledFields] = useState<FormField[] | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);

  async function handleConfirmClick() {
    setBanner(null);
    if (application.ats_type === null) {
      try {
        const updated = await confirmApplication(token, application.id);
        onUpdated(updated);
      } catch (error) {
        setBanner(toBannerContent(error));
      }
      return;
    }

    setIsLoadingForm(true);
    try {
      const form = await getPrefilledForm(token, application.id);
      setPrefilledFields(form.fields);
    } catch (error) {
      setBanner(toBannerContent(error));
    } finally {
      setIsLoadingForm(false);
    }
  }

  async function handleReviewConfirm(fields: FormField[]) {
    setBanner(null);
    setIsConfirming(true);
    try {
      const updated = await confirmApplication(token, application.id, fields);
      setPrefilledFields(null);
      onUpdated(updated);
    } catch (error) {
      setBanner(toBannerContent(error));
    } finally {
      setIsConfirming(false);
    }
  }

  async function handleMarkSent() {
    setBanner(null);
    try {
      const updated = await markApplicationSentManually(token, application.id);
      onUpdated(updated);
    } catch (error) {
      setBanner(toBannerContent(error));
    }
  }

  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-900">{application.job_title}</p>
          <p className="text-sm text-slate-600">{application.company_name}</p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
          {STATUS_LABELS[application.status]}
        </span>
      </div>

      {banner && (
        <div className="mt-3">
          <ErrorBanner content={banner} />
        </div>
      )}
      {application.error_message && (
        <p className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {application.error_message}
        </p>
      )}

      <div className="mt-4">
        <DiagnosticReportView report={application.diagnostic} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <PersonalizedDocumentCard
          title="CV optimisé"
          generatedLabel="Générer CV optimisé"
          onGenerate={() => generateCv(token, application.diagnostic_id)}
          onDownload={() => downloadCv(token, application.diagnostic_id)}
          downloadFilename="cv_optimise.pdf"
        />
        <PersonalizedDocumentCard
          title="Lettre de motivation"
          generatedLabel="Générer lettre de motivation"
          onGenerate={() => generateLetter(token, application.diagnostic_id)}
          onDownload={() => downloadLetter(token, application.diagnostic_id)}
          downloadFilename="lettre_motivation.pdf"
        />
      </div>

      {application.status === "en_cours" && !prefilledFields && (
        <button
          type="button"
          onClick={handleConfirmClick}
          disabled={isLoadingForm}
          className="mt-4 rounded-md bg-blue-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {isLoadingForm ? "Préparation du formulaire..." : "Confirmer la candidature"}
        </button>
      )}

      {prefilledFields && (
        <div className="mt-4">
          <PrefilledFormReview
            fields={prefilledFields}
            onConfirm={handleReviewConfirm}
            onCancel={() => setPrefilledFields(null)}
            isConfirming={isConfirming}
          />
        </div>
      )}

      {application.status === "a_soumettre_manuellement" && (
        <div className="mt-4 flex flex-col gap-2">
          <a
            href={application.offer_url}
            target="_blank"
            rel="noreferrer"
            className="w-fit text-sm font-semibold text-blue-600 underline"
          >
            Ouvrir la page de candidature
          </a>
          <button
            type="button"
            onClick={handleMarkSent}
            className="w-fit rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
          >
            Marquer comme envoyée
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run components/ApplicationCard.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ApplicationCard.tsx frontend/components/ApplicationCard.test.tsx
git commit -m "feat: add ApplicationCard component"
```

---

### Task 8: `JobListingsList` component

**Files:**
- Create: `frontend/components/JobListingsList.tsx`
- Create: `frontend/components/JobListingsList.test.tsx`

**Interfaces:**
- Consumes: `JobListing` (Task 3)
- Produces: `JobListingsList` component — `listings: JobListing[]`, `unavailableSources: string[]`, `onCreateApplications: (selected: JobListing[]) => void`, `isCreating: boolean`

Selection is local `useState` (a `Set<string>` of `JobListing.url`) — nothing is sent to the backend until "Lancer le diagnostic pour la sélection" is clicked, per the spec's two-step validation (free selection, then diagnostic only for what's checked).

- [ ] **Step 1: Write the failing tests**

`frontend/components/JobListingsList.test.tsx`:
```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { JobListingsList } from "./JobListingsList";
import type { JobListing } from "@/lib/types";

const listings: JobListing[] = [
  { title: "Développeur Python", company: "Acme", location: "Paris", snippet: "...", url: "https://example.com/1", source: "adzuna", ats_type: null },
  { title: "Chef de projet", company: "Globex", location: "Lyon", snippet: "...", url: "https://example.com/2", source: "france_travail", ats_type: null },
];

describe("JobListingsList", () => {
  it("renders every listing", () => {
    render(<JobListingsList listings={listings} unavailableSources={[]} onCreateApplications={vi.fn()} isCreating={false} />);
    expect(screen.getByText("Développeur Python")).toBeInTheDocument();
    expect(screen.getByText("Chef de projet")).toBeInTheDocument();
  });

  it("shows a warning for unavailable sources", () => {
    render(<JobListingsList listings={listings} unavailableSources={["france_travail"]} onCreateApplications={vi.fn()} isCreating={false} />);
    expect(screen.getByText(/france_travail/i)).toBeInTheDocument();
  });

  it("disables the create-applications button until at least one listing is checked", () => {
    render(<JobListingsList listings={listings} unavailableSources={[]} onCreateApplications={vi.fn()} isCreating={false} />);
    expect(screen.getByRole("button", { name: /lancer le diagnostic/i })).toBeDisabled();
  });

  it("calls onCreateApplications with only the checked listings", () => {
    const onCreateApplications = vi.fn();
    render(<JobListingsList listings={listings} unavailableSources={[]} onCreateApplications={onCreateApplications} isCreating={false} />);

    fireEvent.click(screen.getByLabelText("Développeur Python"));
    fireEvent.click(screen.getByRole("button", { name: /lancer le diagnostic/i }));

    expect(onCreateApplications).toHaveBeenCalledWith([listings[0]]);
  });

  it("disables the button while creating", () => {
    render(<JobListingsList listings={listings} unavailableSources={[]} onCreateApplications={vi.fn()} isCreating={true} />);
    fireEvent.click(screen.getByLabelText("Développeur Python"));
    expect(screen.getByRole("button", { name: /lancement en cours/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run components/JobListingsList.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement the component**

`frontend/components/JobListingsList.tsx`:
```typescript
"use client";

import { useState } from "react";
import type { JobListing } from "@/lib/types";

interface JobListingsListProps {
  listings: JobListing[];
  unavailableSources: string[];
  onCreateApplications: (selected: JobListing[]) => void;
  isCreating: boolean;
}

export function JobListingsList({ listings, unavailableSources, onCreateApplications, isCreating }: JobListingsListProps) {
  const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());

  function toggle(url: string) {
    setSelectedUrls((prev) => {
      const next = new Set(prev);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });
  }

  function handleCreate() {
    onCreateApplications(listings.filter((listing) => selectedUrls.has(listing.url)));
  }

  return (
    <div>
      {unavailableSources.length > 0 && (
        <p className="mb-3 rounded-md border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-800">
          Sources indisponibles pour cette recherche : {unavailableSources.join(", ")}
        </p>
      )}

      {listings.length === 0 ? (
        <p className="text-sm text-slate-600">Aucune offre trouvée pour ces critères.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {listings.map((listing) => (
            <li key={listing.url} className="flex items-start gap-3 rounded-xl bg-white p-4 shadow-sm">
              <input
                type="checkbox"
                aria-label={listing.title}
                checked={selectedUrls.has(listing.url)}
                onChange={() => toggle(listing.url)}
                className="mt-1"
              />
              <div>
                <p className="text-sm font-semibold text-slate-900">{listing.title}</p>
                <p className="text-sm text-slate-600">
                  {listing.company}
                  {listing.location ? ` — ${listing.location}` : ""}
                </p>
                <p className="mt-1 text-xs text-slate-500">{listing.snippet}</p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={handleCreate}
        disabled={selectedUrls.size === 0 || isCreating}
        className="mt-4 rounded-md bg-blue-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        {isCreating ? "Lancement en cours..." : `Lancer le diagnostic pour la sélection (${selectedUrls.size})`}
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run components/JobListingsList.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/JobListingsList.tsx frontend/components/JobListingsList.test.tsx
git commit -m "feat: add job listings selection component"
```

---

### Task 9: `/candidatures` page

**Files:**
- Create: `frontend/app/candidatures/page.tsx`

**Interfaces:**
- Consumes: `SearchCriteriaForm`, `EMPTY_SEARCH_CRITERIA_FORM_VALUE`, `toSearchCriteria` (Task 4); `JobListingsList` (Task 8); `ApplicationCard` (Task 7); `searchJobs`, `createApplication` (Task 3, Task 5); `RequireAuth`, `ErrorBanner`, `toBannerContent`, `isSessionExpired` (existing)

No test file for this task: this codebase's convention (see `app/diagnostic/page.tsx`, `app/historique/page.tsx` — neither has a `page.test.tsx`) is that page components are composition-only and are covered by their children's component tests plus manual verification, not their own automated test; only the trivial redirect-only root page (`app/page.tsx`) is tested directly. This page follows the same convention: it wires together already-tested components (`SearchCriteriaForm`, `JobListingsList`, `ApplicationCard`) with no new logic of its own beyond passing data between them.

Batch application creation (one `createApplication` call per selected listing) shows only the **last** error encountered if several selected offers fail to create (e.g. one duplicate, one missing-profile) — an accepted V1 simplification; a per-listing error list can be added later if it turns out to matter in practice.

- [ ] **Step 1: Implement the page**

`frontend/app/candidatures/page.tsx`:
```typescript
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import {
  SearchCriteriaForm,
  EMPTY_SEARCH_CRITERIA_FORM_VALUE,
  toSearchCriteria,
  type SearchCriteriaFormValue,
} from "@/components/SearchCriteriaForm";
import { JobListingsList } from "@/components/JobListingsList";
import { ApplicationCard } from "@/components/ApplicationCard";
import { ErrorBanner } from "@/components/ErrorBanner";
import { toBannerContent, isSessionExpired, type BannerContent } from "@/lib/errors";
import { searchJobs, createApplication } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { Application, JobListing, JobSearchResult } from "@/lib/types";

export default function CandidaturesPage() {
  return (
    <RequireAuth>
      <CandidaturesPageContent />
    </RequireAuth>
  );
}

function CandidaturesPageContent() {
  const { token, logout } = useAuth();
  const router = useRouter();
  const [criteria, setCriteria] = useState<SearchCriteriaFormValue>(EMPTY_SEARCH_CRITERIA_FORM_VALUE);
  const [searchResult, setSearchResult] = useState<JobSearchResult | null>(null);
  const [applications, setApplications] = useState<Application[]>([]);
  const [banner, setBanner] = useState<BannerContent | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  function handleAuthError(error: unknown): boolean {
    if (isSessionExpired(error)) {
      logout();
      router.replace("/login");
      return true;
    }
    return false;
  }

  async function handleSearch() {
    if (!token) return;
    setBanner(null);
    setIsSearching(true);
    try {
      const result = await searchJobs(token, toSearchCriteria(criteria));
      setSearchResult(result);
    } catch (error) {
      if (!handleAuthError(error)) setBanner(toBannerContent(error));
    } finally {
      setIsSearching(false);
    }
  }

  async function handleCreateApplications(selected: JobListing[]) {
    if (!token) return;
    setBanner(null);
    setIsCreating(true);
    const created: Application[] = [];
    for (const listing of selected) {
      try {
        const application = await createApplication(token, {
          offer_url: listing.url,
          offer_text: listing.snippet,
          source: listing.source,
          company_name: listing.company,
          job_title: listing.title,
          ats_type: listing.ats_type,
        });
        created.push(application);
      } catch (error) {
        if (handleAuthError(error)) {
          setIsCreating(false);
          return;
        }
        setBanner(toBannerContent(error));
      }
    }
    setApplications((prev) => [...created, ...prev]);
    setIsCreating(false);
  }

  function handleApplicationUpdated(updated: Application) {
    setApplications((prev) => prev.map((application) => (application.id === updated.id ? updated : application)));
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <h1 className="text-xl font-bold text-slate-900">Trouver et postuler à des offres</h1>
      <p className="mt-1 text-sm text-slate-600">
        Définissez vos critères, sélectionnez les offres qui vous intéressent, puis relisez chaque candidature avant
        l&apos;envoi.
      </p>

      <div className="mt-6">
        <SearchCriteriaForm value={criteria} onChange={setCriteria} onSearch={handleSearch} isSearching={isSearching} />
      </div>

      {banner && (
        <div className="mt-4">
          <ErrorBanner content={banner} />
        </div>
      )}

      {searchResult && (
        <div className="mt-6">
          <JobListingsList
            listings={searchResult.listings}
            unavailableSources={searchResult.unavailable_sources}
            onCreateApplications={handleCreateApplications}
            isCreating={isCreating}
          />
        </div>
      )}

      {applications.length > 0 && token && (
        <div className="mt-10 flex flex-col gap-6">
          <h2 className="text-lg font-bold text-slate-900">Vos candidatures</h2>
          {applications.map((application) => (
            <ApplicationCard
              key={application.id}
              application={application}
              token={token}
              onUpdated={handleApplicationUpdated}
            />
          ))}
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Run the full frontend test suite**

Run: `cd frontend && npm test`
Expected: PASS (this page introduces no new logic to unit test — it only wires already-tested components — so this step just confirms it doesn't break the build or any existing test)

- [ ] **Step 3: Manual verification**

Run: `docker compose up` from the repo root, then in a browser: log in, go to `/profil`, fill in the contact fields and upload a reference CV, then go to `/candidatures`, run a search, select an offer, and confirm it in both branches (an offer with `ats_type` set and one without, if test data allows — otherwise confirm at least the assisted-mode branch, since a real Greenhouse/Lever submission requires the mandatory manual verification from the backend plan's Task 15 first). This page's core interaction loop cannot be meaningfully verified by unit tests alone.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/candidatures/page.tsx
git commit -m "feat: add candidatures search-and-apply page"
```

---

### Task 10: Extend `/historique` to list past applications

**Files:**
- Modify: `frontend/app/historique/page.tsx`

**Interfaces:**
- Consumes: `listApplications` (Task 5); `ApplicationCard` (Task 7)

Same no-page-test convention as Task 9. Reuses `ApplicationCard` as-is (rather than a separate read-only summary component) — an application still sitting at `en_cours` or `a_soumettre_manuellement` from a past visit is exactly as actionable from `/historique` as it would be on `/candidatures`, so there is no reason to build a second, less-capable view of the same data. This mirrors how the existing diagnostics list already expands to the full `DiagnosticReportView`, not a stripped-down summary.

- [ ] **Step 1: Implement the extension**

Replace `frontend/app/historique/page.tsx` in full:
```typescript
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import { DiagnosticReportView } from "@/components/DiagnosticReportView";
import { ApplicationCard } from "@/components/ApplicationCard";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { toBannerContent, isSessionExpired, type BannerContent } from "@/lib/errors";
import { listDiagnostics, deleteAllDiagnostics, listApplications } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { Application, DiagnosticReport } from "@/lib/types";

export default function HistoriquePage() {
  return (
    <RequireAuth>
      <HistoriquePageContent />
    </RequireAuth>
  );
}

function HistoriquePageContent() {
  const { token, logout } = useAuth();
  const router = useRouter();
  const [diagnostics, setDiagnostics] = useState<DiagnosticReport[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedApplicationId, setExpandedApplicationId] = useState<number | null>(null);
  const [banner, setBanner] = useState<BannerContent | null>(null);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  function handleAuthError(error: unknown): boolean {
    if (isSessionExpired(error)) {
      logout();
      router.replace("/login");
      return true;
    }
    return false;
  }

  useEffect(() => {
    if (!token) return;
    Promise.all([listDiagnostics(token), listApplications(token)])
      .then(([fetchedDiagnostics, fetchedApplications]) => {
        setDiagnostics(fetchedDiagnostics);
        setApplications(fetchedApplications);
      })
      .catch((error) => {
        if (!handleAuthError(error)) setBanner(toBannerContent(error));
      })
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleDeleteAll() {
    if (!token) return;
    setIsConfirmOpen(false);
    try {
      await deleteAllDiagnostics(token);
      setDiagnostics([]);
      setApplications([]); // RGPD purge cascades to Application rows server-side too
    } catch (error) {
      if (!handleAuthError(error)) setBanner(toBannerContent(error));
    }
  }

  function handleApplicationUpdated(updated: Application) {
    setApplications((prev) => prev.map((application) => (application.id === updated.id ? updated : application)));
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900">Historique</h1>
        {(diagnostics.length > 0 || applications.length > 0) && (
          <button type="button" onClick={() => setIsConfirmOpen(true)} className="text-sm font-semibold text-red-600">
            Supprimer tout mon historique
          </button>
        )}
      </div>

      {banner && (
        <div className="mt-4">
          <ErrorBanner content={banner} />
        </div>
      )}

      {applications.length > 0 && (
        <div className="mt-6">
          <h2 className="text-lg font-bold text-slate-900">Candidatures</h2>
          <ul className="mt-3 flex flex-col gap-3">
            {applications.map((application) => (
              <li key={application.id} className="rounded-xl bg-white p-4 shadow-sm">
                <button
                  type="button"
                  onClick={() => setExpandedApplicationId(expandedApplicationId === application.id ? null : application.id)}
                  className="flex w-full items-center justify-between text-left"
                >
                  <span className="text-sm font-semibold text-slate-900">
                    {application.job_title} — {application.company_name}
                  </span>
                  <span className="text-xs text-slate-500">
                    {new Date(application.created_at).toLocaleDateString("fr-FR")}
                  </span>
                </button>
                {expandedApplicationId === application.id && token && (
                  <div className="mt-4">
                    <ApplicationCard application={application} token={token} onUpdated={handleApplicationUpdated} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-8">
        {applications.length > 0 && <h2 className="text-lg font-bold text-slate-900">Diagnostics</h2>}
        {!isLoading && diagnostics.length === 0 && applications.length === 0 && (
          <p className="mt-6 text-sm text-slate-600">Aucun diagnostic pour le moment.</p>
        )}

        <ul className="mt-3 flex flex-col gap-3">
          {diagnostics.map((diagnostic) => (
            <li key={diagnostic.id} className="rounded-xl bg-white p-4 shadow-sm">
              <button
                type="button"
                onClick={() => setExpandedId(expandedId === diagnostic.id ? null : diagnostic.id)}
                className="flex w-full items-center justify-between text-left"
              >
                <span className="text-sm font-semibold text-slate-900">
                  {new Date(diagnostic.created_at).toLocaleDateString("fr-FR")}
                </span>
                <span className="text-sm font-bold text-blue-600">{diagnostic.overall_score}/100</span>
              </button>
              {expandedId === diagnostic.id && (
                <div className="mt-4">
                  <DiagnosticReportView report={diagnostic} />
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>

      {isConfirmOpen && (
        <ConfirmDialog
          message="Supprimer définitivement tout votre historique de diagnostics et de candidatures ? Cette action est irréversible."
          onConfirm={handleDeleteAll}
          onCancel={() => setIsConfirmOpen(false)}
        />
      )}
    </main>
  );
}
```

- [ ] **Step 2: Run the full frontend test suite**

Run: `cd frontend && npm test`
Expected: PASS

- [ ] **Step 3: Manual verification**

With `docker compose up` running, create at least one application via `/candidatures`, then visit `/historique` and confirm: it appears under "Candidatures", expands to show the full `ApplicationCard`, and "Supprimer tout mon historique" removes it along with any diagnostics.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/historique/page.tsx
git commit -m "feat: list applications in historique"
```

---

## Self-Review

**Spec coverage:**
- `/candidatures`: criteria form → offer selection (free, unpersisted) → diagnostic generation only for selected offers → review (diagnostic + CV/lettre + pre-filled form) → confirm → auto-submit or assisted mode: Tasks 3, 4, 5, 6, 7, 8, 9
- `/profil`: contact fields + reference CV upload, reusing `CVDropzone`: Tasks 1, 2
- `/historique` extended to list applications: Task 10
- Custom fields always shown for review, flagged as LLM-generated: Task 6 (`is_custom` badge, every field editable regardless)
- Reuse of sous-projet 1/3 components unmodified: `DiagnosticReportView` and `PersonalizedDocumentCard` are imported as-is into `ApplicationCard` (Task 7), never edited by this plan
- No new dependencies, French copy, existing patterns (controlled-value forms, self-contained async components, `ErrorBanner`/`toBannerContent`/`isSessionExpired`): true throughout

**Placeholder scan:** no `TBD`/`TODO`; the two tasks without a TDD test step (9, 10) explain why (matches the existing codebase's own convention of leaving page-composition components untested, evidenced by `app/diagnostic/page.tsx` and `app/historique/page.tsx` having no `page.test.tsx`) rather than silently skipping tests.

**Type consistency:** `Application["status"]` string literals match exactly between `lib/types.ts` (Task 5) and the `STATUS_LABELS` record in `ApplicationCard` (Task 7) and the backend's `APPLICATION_STATUS_*` constants (backend plan, Task 2) — `en_cours` / `soumise_auto` / `a_soumettre_manuellement` / `soumise_manuelle_confirmee` / `echec_soumission`. `FormField` (Task 5) is the same shape passed unchanged from `getPrefilledForm`'s response through `ApplicationCard` (Task 7) into `PrefilledFormReview` (Task 6) and back out to `confirmApplication`.
