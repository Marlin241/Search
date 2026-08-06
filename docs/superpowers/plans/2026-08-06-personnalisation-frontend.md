# Personnalisation (CV + lettre) — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "Générer CV optimisé" and "Générer lettre de motivation" actions to the `/diagnostic` page, consuming the backend endpoints built in `docs/superpowers/plans/2026-08-06-personnalisation-backend.md`.

**Architecture:** A new reusable `PersonalizedDocumentCard` component (generate + download + review banners) driven by two new `lib/api.ts` functions per document kind, wired into the existing `/diagnostic` page below the diagnostic report.

**Tech Stack:** Next.js/React (existing app), TypeScript, Vitest + Testing Library (existing test setup).

## Global Constraints

- Requires `docs/superpowers/plans/2026-08-06-personnalisation-backend.md` to be implemented first (the four `/diagnostics/{id}/cv` and `/diagnostics/{id}/lettre` endpoints must exist).
- The two actions ("Générer CV optimisé", "Générer lettre de motivation") only appear on `/diagnostic`, right after a diagnostic has just been created — not on `/historique` (out of scope for this sub-project, see the design spec).
- Every generated document, once ready, must show a persistent "relisez avant d'envoyer" warning banner, plus an additional "à vérifier" badge when the backend reports `needs_review: true` (CV only).
- Regenerating a document simply replaces what's shown — no version history in the UI.

---

### Task 1: API client functions and types

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/api.test.ts`

**Interfaces:**
- Produces: `PersonalizedDocument` type — `kind: "cv" | "lettre"`, `needs_review: boolean`, `created_at: string`, `updated_at: string`
- Produces: `generateCv(token, diagnosticId) -> Promise<PersonalizedDocument>`, `generateLetter(token, diagnosticId) -> Promise<PersonalizedDocument>`
- Produces: `downloadCv(token, diagnosticId) -> Promise<Blob>`, `downloadLetter(token, diagnosticId) -> Promise<Blob>`

- [ ] **Step 1: Write the failing tests**

Append to `frontend/lib/api.test.ts`:
```typescript
import { downloadCv, downloadLetter, generateCv, generateLetter } from "./api";

function blobResponse(content: string, status = 200, contentType = "application/pdf") {
  return {
    ok: status >= 200 && status < 300,
    status,
    blob: async () => new Blob([content], { type: contentType }),
    json: async () => ({ detail: "Erreur" }),
  } as unknown as Response;
}

describe("generateCv", () => {
  it("posts to /diagnostics/:id/cv with the bearer token", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ kind: "cv", needs_review: false, created_at: "2026-08-06T00:00:00Z", updated_at: "2026-08-06T00:00:00Z" }, 201)
    );
    const document = await generateCv("tok123", 42);
    expect(document.kind).toBe("cv");

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/diagnostics/42/cv");
    expect(init?.method).toBe("POST");
    const headers = init?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer tok123");
  });
});

describe("generateLetter", () => {
  it("posts to /diagnostics/:id/lettre", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ kind: "lettre", needs_review: false, created_at: "2026-08-06T00:00:00Z", updated_at: "2026-08-06T00:00:00Z" }, 201)
    );
    const document = await generateLetter("tok123", 42);
    expect(document.kind).toBe("lettre");

    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/diagnostics/42/lettre");
  });
});

describe("downloadCv", () => {
  it("returns a Blob from /diagnostics/:id/cv", async () => {
    vi.mocked(fetch).mockResolvedValue(blobResponse("%PDF-1.4 fake"));
    const blob = await downloadCv("tok123", 42);
    expect(blob).toBeInstanceOf(Blob);

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/diagnostics/42/cv");
    const headers = init?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer tok123");
  });

  it("throws ApiError with the parsed detail on failure", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Aucun CV optimisé n'a encore été généré pour ce diagnostic." }),
    } as Response);

    await expect(downloadCv("tok123", 42)).rejects.toMatchObject({
      status: 404,
      message: "Aucun CV optimisé n'a encore été généré pour ce diagnostic.",
    });
  });
});

describe("downloadLetter", () => {
  it("returns a Blob from /diagnostics/:id/lettre", async () => {
    vi.mocked(fetch).mockResolvedValue(blobResponse("%PDF-1.4 fake"));
    const blob = await downloadLetter("tok123", 42);
    expect(blob).toBeInstanceOf(Blob);

    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/diagnostics/42/lettre");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- api.test.ts`
Expected: FAIL with `generateCv is not a function` (or similar — the exports don't exist yet)

- [ ] **Step 3: Implement the type and API functions**

Modify `frontend/lib/types.ts` — append:
```typescript
export interface PersonalizedDocument {
  kind: "cv" | "lettre";
  needs_review: boolean;
  created_at: string;
  updated_at: string;
}
```

Modify `frontend/lib/api.ts` — add the import and the four new functions at the end of the file:
```typescript
import type { DiagnosticReport, PersonalizedDocument, User } from "./types";
```

```typescript
async function requestBlob(path: string, token: string): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new ApiError(0, "Impossible de contacter le serveur.");
  }
  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response));
  }
  return response.blob();
}

export function generateCv(token: string, diagnosticId: number): Promise<PersonalizedDocument> {
  return request<PersonalizedDocument>(`/diagnostics/${diagnosticId}/cv`, { method: "POST" }, token);
}

export function generateLetter(token: string, diagnosticId: number): Promise<PersonalizedDocument> {
  return request<PersonalizedDocument>(`/diagnostics/${diagnosticId}/lettre`, { method: "POST" }, token);
}

export function downloadCv(token: string, diagnosticId: number): Promise<Blob> {
  return requestBlob(`/diagnostics/${diagnosticId}/cv`, token);
}

export function downloadLetter(token: string, diagnosticId: number): Promise<Blob> {
  return requestBlob(`/diagnostics/${diagnosticId}/lettre`, token);
}
```

`requestBlob` mirrors the existing private `request<T>` helper but returns a `Blob` via `response.blob()` instead of parsing JSON, since PDF downloads aren't JSON. It reuses the same `parseErrorDetail` helper already defined earlier in the file for consistent error messages.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- api.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts frontend/lib/api.test.ts
git commit -m "feat: add CV/lettre generation and download API client functions"
```

---

### Task 2: `PersonalizedDocumentCard` component

**Files:**
- Create: `frontend/components/PersonalizedDocumentCard.tsx`
- Create: `frontend/components/PersonalizedDocumentCard.test.tsx`

**Interfaces:**
- Consumes: `PersonalizedDocument` (Task 1), `ErrorBanner` (existing), `toBannerContent`/`BannerContent` (existing, `lib/errors.ts`)
- Produces: `PersonalizedDocumentCard` component — props `title: string`, `generatedLabel: string`, `onGenerate: () => Promise<PersonalizedDocument>`, `onDownload: () => Promise<Blob>`, `downloadFilename: string`

- [ ] **Step 1: Write the failing tests**

`frontend/components/PersonalizedDocumentCard.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { PersonalizedDocumentCard } from "./PersonalizedDocumentCard";
import { ApiError } from "@/lib/api";

const baseProps = {
  title: "CV optimisé",
  generatedLabel: "Générer CV optimisé",
  downloadFilename: "cv_optimise.pdf",
};

describe("PersonalizedDocumentCard", () => {
  it("shows the generate button initially", () => {
    render(<PersonalizedDocumentCard {...baseProps} onGenerate={vi.fn()} onDownload={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Générer CV optimisé" })).toBeInTheDocument();
  });

  it("generates the document and shows the review banner and download button", async () => {
    const onGenerate = vi.fn().mockResolvedValue({
      kind: "cv",
      needs_review: false,
      created_at: "2026-08-06T00:00:00Z",
      updated_at: "2026-08-06T00:00:00Z",
    });
    render(<PersonalizedDocumentCard {...baseProps} onGenerate={onGenerate} onDownload={vi.fn()} />);

    screen.getByRole("button", { name: "Générer CV optimisé" }).click();

    await waitFor(() => expect(onGenerate).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/relisez ce document/i)).toBeInTheDocument();
    expect(screen.queryByText(/à vérifier/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Télécharger" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Régénérer" })).toBeInTheDocument();
  });

  it("shows an additional badge when needs_review is true", async () => {
    const onGenerate = vi.fn().mockResolvedValue({
      kind: "cv",
      needs_review: true,
      created_at: "2026-08-06T00:00:00Z",
      updated_at: "2026-08-06T00:00:00Z",
    });
    render(<PersonalizedDocumentCard {...baseProps} onGenerate={onGenerate} onDownload={vi.fn()} />);

    screen.getByRole("button", { name: "Générer CV optimisé" }).click();

    expect(await screen.findByText(/à vérifier/i)).toBeInTheDocument();
  });

  it("shows an error banner when generation fails", async () => {
    const onGenerate = vi.fn().mockRejectedValue(new ApiError(503, "Le service est indisponible."));
    render(<PersonalizedDocumentCard {...baseProps} onGenerate={onGenerate} onDownload={vi.fn()} />);

    screen.getByRole("button", { name: "Générer CV optimisé" }).click();

    expect(await screen.findByRole("alert")).toHaveTextContent("Le service est indisponible.");
  });

  it("calls onDownload when the download button is clicked", async () => {
    const onGenerate = vi.fn().mockResolvedValue({
      kind: "cv",
      needs_review: false,
      created_at: "2026-08-06T00:00:00Z",
      updated_at: "2026-08-06T00:00:00Z",
    });
    const onDownload = vi.fn().mockResolvedValue(new Blob(["%PDF-1.4"], { type: "application/pdf" }));
    // jsdom doesn't implement createObjectURL/revokeObjectURL — stub them.
    URL.createObjectURL = vi.fn().mockReturnValue("blob:mock-url");
    URL.revokeObjectURL = vi.fn();

    render(<PersonalizedDocumentCard {...baseProps} onGenerate={onGenerate} onDownload={onDownload} />);
    screen.getByRole("button", { name: "Générer CV optimisé" }).click();
    const downloadButton = await screen.findByRole("button", { name: "Télécharger" });

    downloadButton.click();

    await waitFor(() => expect(onDownload).toHaveBeenCalledTimes(1));
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- PersonalizedDocumentCard.test.tsx`
Expected: FAIL — `Failed to resolve import "./PersonalizedDocumentCard"`

- [ ] **Step 3: Implement the component**

`frontend/components/PersonalizedDocumentCard.tsx`:
```tsx
"use client";

import { useState } from "react";
import { ErrorBanner } from "./ErrorBanner";
import { toBannerContent, type BannerContent } from "@/lib/errors";
import type { PersonalizedDocument } from "@/lib/types";

interface PersonalizedDocumentCardProps {
  title: string;
  generatedLabel: string;
  onGenerate: () => Promise<PersonalizedDocument>;
  onDownload: () => Promise<Blob>;
  downloadFilename: string;
}

export function PersonalizedDocumentCard({
  title,
  generatedLabel,
  onGenerate,
  onDownload,
  downloadFilename,
}: PersonalizedDocumentCardProps) {
  const [generatedDocument, setGeneratedDocument] = useState<PersonalizedDocument | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [banner, setBanner] = useState<BannerContent | null>(null);

  async function handleGenerate() {
    setBanner(null);
    setIsGenerating(true);
    try {
      const result = await onGenerate();
      setGeneratedDocument(result);
    } catch (error) {
      setBanner(toBannerContent(error));
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleDownload() {
    setBanner(null);
    try {
      const blob = await onDownload();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = downloadFilename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setBanner(toBannerContent(error));
    }
  }

  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <p className="text-sm font-semibold text-slate-900">{title}</p>

      {banner && (
        <div className="mt-2">
          <ErrorBanner content={banner} />
        </div>
      )}

      {!generatedDocument && (
        <button
          type="button"
          onClick={handleGenerate}
          disabled={isGenerating}
          className="mt-2 rounded-md bg-blue-500 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {isGenerating ? "Génération en cours..." : generatedLabel}
        </button>
      )}

      {generatedDocument && (
        <div className="mt-2 flex flex-col gap-2">
          <p className="rounded-md border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-800">
            Relisez ce document avant de l&apos;envoyer.
          </p>
          {generatedDocument.needs_review && (
            <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              À vérifier : ce document pourrait contenir des éléments absents de votre CV d&apos;origine.
            </p>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleDownload}
              className="rounded-md bg-blue-500 px-3 py-2 text-sm font-semibold text-white"
            >
              Télécharger
            </button>
            <button
              type="button"
              onClick={handleGenerate}
              disabled={isGenerating}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50"
            >
              {isGenerating ? "Génération en cours..." : "Régénérer"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
```

The generated document is kept in local state (`generatedDocument`) rather than fetched separately — a regeneration simply calls `onGenerate` again and replaces it, matching the "no version history" design decision.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- PersonalizedDocumentCard.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/PersonalizedDocumentCard.tsx frontend/components/PersonalizedDocumentCard.test.tsx
git commit -m "feat: add PersonalizedDocumentCard component"
```

---

### Task 3: Wire the actions into `/diagnostic`

**Files:**
- Modify: `frontend/app/diagnostic/page.tsx`

**Interfaces:**
- Consumes: `PersonalizedDocumentCard` (Task 2), `generateCv`/`generateLetter`/`downloadCv`/`downloadLetter` (Task 1)

This task has no new unit-testable logic of its own — `DiagnosticPage` isn't covered by a component test today (per the project's existing testing conventions, noted in the diagnostic-ats spec: "tests légers pour cette V1 ... le risque principal du projet étant côté backend"). Verify it manually per Step 3 below instead of with an automated test.

- [ ] **Step 1: Modify `frontend/app/diagnostic/page.tsx`**

Add the new imports at the top of the file:
```typescript
import { PersonalizedDocumentCard } from "@/components/PersonalizedDocumentCard";
import { createDiagnostic, downloadCv, downloadLetter, generateCv, generateLetter } from "@/lib/api";
```

(`createDiagnostic` is already imported today — just add the four new names to that same import line instead of duplicating it.)

Replace the report-rendering block near the end of the component:
```tsx
      {report && (
        <div className="mt-10">
          <DiagnosticReportView report={report} />
        </div>
      )}
```

with:
```tsx
      {report && (
        <div className="mt-10 flex flex-col gap-6">
          <DiagnosticReportView report={report} />
          {token && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <PersonalizedDocumentCard
                title="CV optimisé"
                generatedLabel="Générer CV optimisé"
                onGenerate={() => generateCv(token, report.id)}
                onDownload={() => downloadCv(token, report.id)}
                downloadFilename="cv_optimise.pdf"
              />
              <PersonalizedDocumentCard
                title="Lettre de motivation"
                generatedLabel="Générer lettre de motivation"
                onGenerate={() => generateLetter(token, report.id)}
                onDownload={() => downloadLetter(token, report.id)}
                downloadFilename="lettre_motivation.pdf"
              />
            </div>
          )}
        </div>
      )}
```

`token` is already destructured from `useAuth()` at the top of `DiagnosticPageContent` (used by the existing `handleSubmit`). The `{token && (...)}` guard avoids a non-null assertion — in practice `token` is always set here since the whole page is wrapped in `<RequireAuth>`, but this keeps TypeScript happy without `!`.

- [ ] **Step 2: Run the full frontend test suite to confirm nothing broke**

Run: `cd frontend && npm test`
Expected: PASS (all existing tests plus the ones added in Tasks 1-2)

- [ ] **Step 3: Manual verification**

With the backend (Task plan: `2026-08-06-personnalisation-backend.md`) and `docker compose up --build` running:
1. Log in, upload a CV, submit an offer, and get a diagnostic on `/diagnostic`.
2. Click "Générer CV optimisé" — verify a PDF downloads via the "Télécharger" button, and that the "relisez avant d'envoyer" banner is visible.
3. Click "Régénérer" — verify the card updates without a page reload.
4. Click "Générer lettre de motivation" — verify a separate PDF downloads.
5. Trigger the personalization rate limit (11 rapid generations) — verify a clear error banner appears instead of a silent failure.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/diagnostic/page.tsx
git commit -m "feat: wire CV/lettre generation into the diagnostic page"
```

---
