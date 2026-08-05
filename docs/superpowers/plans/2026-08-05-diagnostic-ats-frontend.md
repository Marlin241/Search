# Diagnostic ATS — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Next.js/React frontend for the ATS diagnostic tool: users register/log in, upload a CV plus a job offer, see a diagnostic report (scores + issues + missing keywords + recommendations), and browse/purge their diagnostic history — all consuming the existing FastAPI backend in `backend/`.

**Architecture:** Next.js 14 App Router SPA-style app (client components throughout, since auth state lives in `localStorage`). A hand-written typed `fetch` wrapper (`lib/api.ts`) is the only data-fetching layer — no React Query/SWR. A React `AuthContext` holds the JWT and current user, backed by `localStorage`. Tailwind CSS for styling, following the "rassurant" (blue accent, progress-circle) visual identity validated during brainstorming.

**Tech Stack:** Next.js 14+, React 18, TypeScript (strict), Tailwind CSS 3, Vitest + React Testing Library + jsdom for component tests.

## Global Constraints

- Backend prerequisite: `DiagnosticReport` must expose `id` and `created_at` (Task 1) before any frontend history work begins.
- Next.js 14+ App Router, TypeScript strict mode, Tailwind CSS v3.
- API base URL from `NEXT_PUBLIC_API_URL` env var, default `http://localhost:8000` (backend CORS already allows `http://localhost:3000`, the Next.js dev server's default port).
- JWT stored in `localStorage` under the key `ats_diagnostic_token`.
- Max CV upload size validated client-side: 5 MB (5 * 1024 * 1024 bytes), mirroring the backend's `MAX_CV_SIZE_BYTES`.
- Supported CV formats client-side: `.pdf`, `.docx` only.
- UI language: French only — no i18n of interface labels (the FR/EN support is for CV/offer *content*, handled entirely by the backend).
- Visual identity: blue `#3b82f6` accent on `slate-50`/white background, circular progress indicators for scores, encouraging/coach-toned copy rather than alarmist — validated via brainstorm mockup.
- No per-item diagnostic deletion in the UI — the backend only supports purging the entire history (`DELETE /diagnostics`), so the history page only offers "supprimer tout mon historique" behind a confirmation dialog.
- Tests: Vitest + React Testing Library for isolated logic/components only, per task. No E2E. Full-page compositions (`/login`, `/diagnostic`, `/historique`) are verified by manual QA (documented in Task 16), not automated tests, per the project spec's "tests légers côté frontend" stance — their building blocks are already covered by component tests.
- Never commit `frontend/node_modules/`, `frontend/.next/`, or `frontend/.env.local`.

---

### Task 1: Backend — expose `id` and `created_at` on `DiagnosticReport`

**Files:**
- Modify: `backend/app/schemas/diagnostic.py`
- Modify: `backend/app/routers/diagnostics.py`
- Modify: `backend/tests/routers/test_diagnostics.py`

**Interfaces:**
- Consumes: `Diagnostic` ORM model (`id: int`, `created_at: datetime`, already defined in `backend/app/models/diagnostic.py`)
- Produces: `DiagnosticReport` now includes `id: int | None`, `created_at: datetime | None` (defaulting to `None` so `app.aggregator.aggregator.build_diagnostic_report` — which has no DB row yet — keeps working unmodified). Both fields are always populated by the time a response leaves `POST/GET /diagnostics`.

- [ ] **Step 1: Write the failing test assertions**

Modify `backend/tests/routers/test_diagnostics.py` — in `test_create_diagnostic_returns_combined_report`, add after the existing asserts:

```python
    assert isinstance(body["id"], int)
    assert body["created_at"]
```

Add a new test at the end of the file:

```python
def test_list_diagnostics_includes_id_and_created_at_newest_first(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(
        "/diagnostics",
        headers=headers,
        files={"cv_file": ("cv.docx", _clean_cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"offer_text": "We need a Python developer."},
    ).json()
    second = client.post(
        "/diagnostics",
        headers=headers,
        files={"cv_file": ("cv.docx", _clean_cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"offer_text": "We need a Python developer."},
    ).json()

    listed = client.get("/diagnostics", headers=headers).json()

    assert [d["id"] for d in listed] == [second["id"], first["id"]]
    assert all("created_at" in d for d in listed)

    app.dependency_overrides.pop(get_semantic_analyzer, None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/routers/test_diagnostics.py -v`
Expected: FAIL — `body["id"]` is `None` (schema doesn't populate it), `KeyError`-style assertion failures on the new test.

- [ ] **Step 3: Update the schema**

`backend/app/schemas/diagnostic.py`:

```python
from datetime import datetime

from pydantic import BaseModel


class DiagnosticReport(BaseModel):
    id: int | None = None
    created_at: datetime | None = None
    overall_score: int
    structural_score: int
    structural_issues: list[str]
    semantic_score: int
    missing_keywords: list[str]
    recommendations: list[str]
```

- [ ] **Step 4: Populate the fields in the router**

In `backend/app/routers/diagnostics.py`, replace the diagnostic-creation block (the `db.add(Diagnostic(...))` call through `return report`) with:

```python
    diagnostic = Diagnostic(
        user_id=current_user.id,
        cv_text=parsed_cv.text,
        offer_text=offer,
        overall_score=report.overall_score,
        structural_score=report.structural_score,
        structural_issues=report.structural_issues,
        semantic_score=report.semantic_score,
        missing_keywords=report.missing_keywords,
        recommendations=report.recommendations,
    )
    db.add(diagnostic)
    db.commit()
    db.refresh(diagnostic)

    return report.model_copy(update={"id": diagnostic.id, "created_at": diagnostic.created_at})
```

And in `list_diagnostics`, replace the list comprehension with:

```python
    return [
        DiagnosticReport(
            id=d.id,
            created_at=d.created_at,
            overall_score=d.overall_score,
            structural_score=d.structural_score,
            structural_issues=d.structural_issues,
            semantic_score=d.semantic_score,
            missing_keywords=d.missing_keywords,
            recommendations=d.recommendations,
        )
        for d in diagnostics
    ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/routers/test_diagnostics.py -v`
Expected: PASS

Run the full backend suite to make sure nothing else broke: `cd backend && pytest -v`
Expected: PASS (all tests, including `tests/aggregator/test_aggregator.py`, which is unaffected since `id`/`created_at` default to `None`)

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/schemas/diagnostic.py app/routers/diagnostics.py tests/routers/test_diagnostics.py
git commit -m "feat: expose id and created_at on DiagnosticReport for frontend history"
```

---

### Task 2: Frontend project scaffolding

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.mjs`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.mjs`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Create: `frontend/.env.local.example`
- Create: `frontend/app/globals.css`
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/page.tsx`
- Test: `frontend/app/page.test.tsx`
- Modify: `.gitignore` (repo root)

**Interfaces:**
- Produces: a working Next.js dev/build pipeline and a Vitest pipeline, both green, that every later task builds on. `app/page.tsx` here is a temporary placeholder — Task 15 replaces it with the real redirect logic.

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "diagnostic-ats-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run"
  },
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "@types/node": "^20.14.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "vitest": "^2.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^24.1.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.4.0"
  }
}
```

- [ ] **Step 2: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create `frontend/next.config.mjs`**

```js
/** @type {import('next').NextConfig} */
const nextConfig = {};

export default nextConfig;
```

- [ ] **Step 4: Create `frontend/tailwind.config.ts`**

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};

export default config;
```

- [ ] **Step 5: Create `frontend/postcss.config.mjs`**

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 6: Create `frontend/vitest.config.ts` and `frontend/vitest.setup.ts`**

`frontend/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
```

`frontend/vitest.setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 7: Create `frontend/.env.local.example`**

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 8: Create `frontend/app/globals.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 9: Create `frontend/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Diagnostic ATS",
  description: "Comprendre pourquoi votre CV est mal traité par les ATS.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="min-h-screen bg-slate-50 text-slate-900">{children}</body>
    </html>
  );
}
```

- [ ] **Step 10: Write the failing test for the placeholder home page**

`frontend/app/page.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Home from "./page";

describe("Home page placeholder", () => {
  it("renders the app name", () => {
    render(<Home />);
    expect(screen.getByText("Diagnostic ATS")).toBeInTheDocument();
  });
});
```

- [ ] **Step 11: Install dependencies and run the test to verify it fails**

Run: `cd frontend && npm install && npx vitest run app/page.test.tsx`
Expected: FAIL — `./page` (i.e. `app/page.tsx`) does not exist yet.

- [ ] **Step 12: Create the placeholder home page**

`frontend/app/page.tsx`:

```tsx
export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center">
      <h1 className="text-2xl font-bold text-slate-900">Diagnostic ATS</h1>
    </main>
  );
}
```

- [ ] **Step 13: Run the test to verify it passes**

Run: `cd frontend && npx vitest run app/page.test.tsx`
Expected: PASS

- [ ] **Step 14: Verify the production build compiles**

Run: `cd frontend && npm run build`
Expected: PASS (this also generates `next-env.d.ts`, which should not be committed — Next.js's default `.gitignore` output already excludes it, but since we're hand-rolling scaffolding, verify it doesn't get staged in the next step)

- [ ] **Step 15: Add frontend entries to the root `.gitignore`**

Append to `/home/roland/Documents/Search/.gitignore`:

```
frontend/node_modules/
frontend/.next/
frontend/.env.local
frontend/next-env.d.ts
```

- [ ] **Step 16: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/next.config.mjs frontend/tailwind.config.ts frontend/postcss.config.mjs frontend/vitest.config.ts frontend/vitest.setup.ts frontend/.env.local.example frontend/app/globals.css frontend/app/layout.tsx frontend/app/page.tsx frontend/app/page.test.tsx .gitignore
git commit -m "feat: scaffold Next.js frontend with Tailwind and Vitest"
```

---

### Task 3: Shared types + API client

**Files:**
- Create: `frontend/lib/types.ts`
- Create: `frontend/lib/api.ts`
- Test: `frontend/lib/api.test.ts`

**Interfaces:**
- Produces: `User` (`id: number`, `email: string`), `DiagnosticReport` (`id: number`, `created_at: string`, `overall_score: number`, `structural_score: number`, `structural_issues: string[]`, `semantic_score: number`, `missing_keywords: string[]`, `recommendations: string[]`) in `lib/types.ts`
- Produces: `ApiError` (class, `status: number`, `message` inherited from `Error`), `register(email, password): Promise<User>`, `login(email, password): Promise<{access_token: string; token_type: string}>`, `fetchMe(token): Promise<User>`, `createDiagnostic(token, cvFile, offer: {text?: string; url?: string}): Promise<DiagnosticReport>`, `listDiagnostics(token): Promise<DiagnosticReport[]>`, `deleteAllDiagnostics(token): Promise<void>` in `lib/api.ts`

- [ ] **Step 1: Create the shared types**

`frontend/lib/types.ts`:

```ts
export interface User {
  id: number;
  email: string;
}

export interface DiagnosticReport {
  id: number;
  created_at: string;
  overall_score: number;
  structural_score: number;
  structural_issues: string[];
  semantic_score: number;
  missing_keywords: string[];
  recommendations: string[];
}
```

- [ ] **Step 2: Write the failing tests**

`frontend/lib/api.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError, register, login, fetchMe, createDiagnostic, listDiagnostics, deleteAllDiagnostics } from "./api";

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

describe("register", () => {
  it("posts JSON to /auth/register", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ id: 1, email: "jane@example.com" }, 201));
    const user = await register("jane@example.com", "s3cret!");
    expect(user.email).toBe("jane@example.com");

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/auth/register");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({ email: "jane@example.com", password: "s3cret!" });
  });
});

describe("login", () => {
  it("posts form-encoded credentials to /auth/login", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ access_token: "tok", token_type: "bearer" }));
    const result = await login("jane@example.com", "s3cret!");
    expect(result.access_token).toBe("tok");

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/auth/login");
    expect(init?.body).toBe("username=jane%40example.com&password=s3cret%21");
  });
});

describe("fetchMe", () => {
  it("sends the bearer token", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ id: 1, email: "jane@example.com" }));
    await fetchMe("tok123");

    const [, init] = vi.mocked(fetch).mock.calls[0];
    const headers = init?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer tok123");
  });
});

describe("createDiagnostic", () => {
  it("builds multipart form data with only the active offer field", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        id: 1,
        created_at: "2026-08-05T00:00:00Z",
        overall_score: 80,
        structural_score: 90,
        structural_issues: [],
        semantic_score: 70,
        missing_keywords: [],
        recommendations: [],
      })
    );
    const file = new File(["content"], "cv.pdf", { type: "application/pdf" });
    await createDiagnostic("tok123", file, { text: "Offer text" });

    const [, init] = vi.mocked(fetch).mock.calls[0];
    const body = init?.body as FormData;
    expect(body.get("cv_file")).toBe(file);
    expect(body.get("offer_text")).toBe("Offer text");
    expect(body.get("offer_url")).toBeNull();
  });
});

describe("listDiagnostics / deleteAllDiagnostics", () => {
  it("lists diagnostics", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse([]));
    const result = await listDiagnostics("tok123");
    expect(result).toEqual([]);
  });

  it("deletes without parsing a body on 204", async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: true, status: 204, json: async () => { throw new Error("no body"); } } as Response);
    await expect(deleteAllDiagnostics("tok123")).resolves.toBeUndefined();
  });
});

describe("error handling", () => {
  it("throws an ApiError with the backend's detail message on a non-2xx response", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ detail: "Cet email est déjà utilisé." }, 409));
    await expect(register("dup@example.com", "pw")).rejects.toMatchObject({
      status: 409,
      message: "Cet email est déjà utilisé.",
    });
  });

  it("throws a status-0 ApiError when fetch itself fails", async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError("network down"));
    await expect(login("jane@example.com", "pw")).rejects.toMatchObject({
      status: 0,
      message: "Impossible de contacter le serveur.",
    });
  });
});

it("ApiError is an instance of Error", () => {
  const error = new ApiError(422, "Invalid input");
  expect(error).toBeInstanceOf(Error);
  expect(error.status).toBe(422);
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: FAIL — `./api` does not exist yet.

- [ ] **Step 4: Implement the API client**

`frontend/lib/api.ts`:

```ts
import type { DiagnosticReport, User } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // response body wasn't JSON — fall through to the generic message
  }
  return "Une erreur est survenue.";
}

async function request<T>(path: string, init: RequestInit, token?: string | null): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Impossible de contacter le serveur.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function register(email: string, password: string): Promise<User> {
  return request<User>("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function login(email: string, password: string): Promise<{ access_token: string; token_type: string }> {
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);
  return request("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });
}

export function fetchMe(token: string): Promise<User> {
  return request<User>("/auth/me", { method: "GET" }, token);
}

export function createDiagnostic(
  token: string,
  cvFile: File,
  offer: { text?: string; url?: string }
): Promise<DiagnosticReport> {
  const formData = new FormData();
  formData.append("cv_file", cvFile);
  if (offer.text) formData.append("offer_text", offer.text);
  if (offer.url) formData.append("offer_url", offer.url);
  return request<DiagnosticReport>("/diagnostics", { method: "POST", body: formData }, token);
}

export function listDiagnostics(token: string): Promise<DiagnosticReport[]> {
  return request<DiagnosticReport[]>("/diagnostics", { method: "GET" }, token);
}

export function deleteAllDiagnostics(token: string): Promise<void> {
  return request<void>("/diagnostics", { method: "DELETE" }, token);
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd frontend && git add lib/types.ts lib/api.ts lib/api.test.ts
git commit -m "feat: add typed API client for the FastAPI backend"
```

---

### Task 4: Auth context & provider

**Files:**
- Create: `frontend/context/AuthContext.tsx`
- Test: `frontend/context/AuthContext.test.tsx`
- Modify: `frontend/app/layout.tsx`

**Interfaces:**
- Consumes: `register`, `login`, `fetchMe`, `ApiError` from `lib/api` (Task 3); `User` from `lib/types` (Task 3)
- Produces: `AuthProvider` (component), `useAuth(): { user: User | null; token: string | null; isLoading: boolean; login(email, password): Promise<void>; register(email, password): Promise<void>; logout(): void }` in `context/AuthContext.tsx`. Token persisted under `localStorage["ats_diagnostic_token"]`.

- [ ] **Step 1: Write the failing tests**

`frontend/context/AuthContext.test.tsx`:

```tsx
import { render, screen, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  login: vi.fn(),
  register: vi.fn(),
  fetchMe: vi.fn(),
}));

function Probe() {
  const { user, token, isLoading, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="token">{token ?? "none"}</span>
      <span data-testid="email">{user?.email ?? "none"}</span>
      <button onClick={() => login("jane@example.com", "pw")}>login</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(api.login).mockReset();
  vi.mocked(api.fetchMe).mockReset();
});

describe("AuthProvider", () => {
  it("starts with no token when localStorage is empty", async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
    expect(screen.getByTestId("token").textContent).toBe("none");
  });

  it("restores the user from a token already in localStorage", async () => {
    localStorage.setItem("ats_diagnostic_token", "existing-token");
    vi.mocked(api.fetchMe).mockResolvedValue({ id: 2, email: "restored@example.com" });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("email").textContent).toBe("restored@example.com"));
    expect(api.fetchMe).toHaveBeenCalledWith("existing-token");
  });

  it("clears an invalid stored token", async () => {
    localStorage.setItem("ats_diagnostic_token", "bad-token");
    vi.mocked(api.fetchMe).mockRejectedValue(new Error("401"));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
    expect(screen.getByTestId("token").textContent).toBe("none");
    expect(localStorage.getItem("ats_diagnostic_token")).toBeNull();
  });

  it("login stores the token and exposes the user", async () => {
    vi.mocked(api.login).mockResolvedValue({ access_token: "abc123", token_type: "bearer" });
    vi.mocked(api.fetchMe).mockResolvedValue({ id: 1, email: "jane@example.com" });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));

    await act(async () => {
      screen.getByText("login").click();
    });

    await waitFor(() => expect(screen.getByTestId("token").textContent).toBe("abc123"));
    expect(screen.getByTestId("email").textContent).toBe("jane@example.com");
    expect(localStorage.getItem("ats_diagnostic_token")).toBe("abc123");
  });

  it("logout clears the token", async () => {
    vi.mocked(api.login).mockResolvedValue({ access_token: "abc123", token_type: "bearer" });
    vi.mocked(api.fetchMe).mockResolvedValue({ id: 1, email: "jane@example.com" });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
    await act(async () => {
      screen.getByText("login").click();
    });
    await waitFor(() => expect(screen.getByTestId("token").textContent).toBe("abc123"));

    await act(async () => {
      screen.getByText("logout").click();
    });

    expect(screen.getByTestId("token").textContent).toBe("none");
    expect(localStorage.getItem("ats_diagnostic_token")).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run context/AuthContext.test.tsx`
Expected: FAIL — `./AuthContext` does not exist yet.

- [ ] **Step 3: Implement the auth context**

`frontend/context/AuthContext.tsx`:

```tsx
"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { login as apiLogin, register as apiRegister, fetchMe } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const TOKEN_STORAGE_KEY = "ats_diagnostic_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!stored) {
      setIsLoading(false);
      return;
    }
    fetchMe(stored)
      .then((fetchedUser) => {
        setToken(stored);
        setUser(fetchedUser);
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
      })
      .finally(() => setIsLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const { access_token } = await apiLogin(email, password);
    const loggedInUser = await fetchMe(access_token);
    localStorage.setItem(TOKEN_STORAGE_KEY, access_token);
    setToken(access_token);
    setUser(loggedInUser);
  }

  async function register(email: string, password: string) {
    await apiRegister(email, password);
    await login(email, password);
  }

  function logout() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run context/AuthContext.test.tsx`
Expected: PASS

- [ ] **Step 5: Wrap the app in `AuthProvider`**

Modify `frontend/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";

export const metadata: Metadata = {
  title: "Diagnostic ATS",
  description: "Comprendre pourquoi votre CV est mal traité par les ATS.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="min-h-screen bg-slate-50 text-slate-900">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 6: Verify the build still compiles**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
cd frontend && git add context/AuthContext.tsx context/AuthContext.test.tsx app/layout.tsx
git commit -m "feat: add AuthContext with localStorage-backed JWT session"
```

---

### Task 5: `RequireAuth` guard

**Files:**
- Create: `frontend/components/RequireAuth.tsx`
- Test: `frontend/components/RequireAuth.test.tsx`

**Interfaces:**
- Consumes: `useAuth()` from `context/AuthContext` (Task 4)
- Produces: `RequireAuth({ children }: { children: ReactNode })` in `components/RequireAuth.tsx` — renders `children` only when authenticated, otherwise redirects to `/login`

- [ ] **Step 1: Write the failing tests**

`frontend/components/RequireAuth.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { RequireAuth } from "./RequireAuth";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

const useAuthMock = vi.fn();
vi.mock("@/context/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

beforeEach(() => {
  replaceMock.mockReset();
  useAuthMock.mockReset();
});

describe("RequireAuth", () => {
  it("redirects to /login when there is no token and loading is finished", async () => {
    useAuthMock.mockReturnValue({ token: null, isLoading: false });
    render(
      <RequireAuth>
        <p>secret</p>
      </RequireAuth>
    );
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("renders children when a token is present", () => {
    useAuthMock.mockReturnValue({ token: "abc", isLoading: false });
    render(
      <RequireAuth>
        <p>secret</p>
      </RequireAuth>
    );
    expect(screen.getByText("secret")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("renders nothing while loading", () => {
    useAuthMock.mockReturnValue({ token: null, isLoading: true });
    render(
      <RequireAuth>
        <p>secret</p>
      </RequireAuth>
    );
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run components/RequireAuth.test.tsx`
Expected: FAIL — `./RequireAuth` does not exist yet.

- [ ] **Step 3: Implement `RequireAuth`**

`frontend/components/RequireAuth.tsx`:

```tsx
"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { token, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !token) {
      router.replace("/login");
    }
  }, [isLoading, token, router]);

  if (isLoading || !token) return null;
  return <>{children}</>;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run components/RequireAuth.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd frontend && git add components/RequireAuth.tsx components/RequireAuth.test.tsx
git commit -m "feat: add RequireAuth route guard"
```

---

### Task 6: `ScoreCircle` component

**Files:**
- Create: `frontend/components/ScoreCircle.tsx`
- Test: `frontend/components/ScoreCircle.test.tsx`

**Interfaces:**
- Produces: `ScoreCircle({ score: number; size?: "lg" | "sm"; label?: string })` in `components/ScoreCircle.tsx` — renders a blue SVG progress circle with the score in the center, clamped to `[0, 100]`.

- [ ] **Step 1: Write the failing tests**

`frontend/components/ScoreCircle.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ScoreCircle } from "./ScoreCircle";

describe("ScoreCircle", () => {
  it("renders the score", () => {
    render(<ScoreCircle score={62} />);
    expect(screen.getByText("62")).toBeInTheDocument();
  });

  it("clamps scores above 100 down to 100", () => {
    render(<ScoreCircle score={140} />);
    expect(screen.getByText("100")).toBeInTheDocument();
  });

  it("clamps negative scores up to 0", () => {
    render(<ScoreCircle score={-10} />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("renders an optional label", () => {
    render(<ScoreCircle score={80} label="Structure" />);
    expect(screen.getByText("Structure")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run components/ScoreCircle.test.tsx`
Expected: FAIL — `./ScoreCircle` does not exist yet.

- [ ] **Step 3: Implement `ScoreCircle`**

`frontend/components/ScoreCircle.tsx`:

```tsx
interface ScoreCircleProps {
  score: number;
  size?: "lg" | "sm";
  label?: string;
}

const SIZES = {
  lg: { diameter: 96, stroke: 8, fontSize: "text-2xl" },
  sm: { diameter: 56, stroke: 6, fontSize: "text-base" },
} as const;

export function ScoreCircle({ score, size = "lg", label }: ScoreCircleProps) {
  const clamped = Math.min(100, Math.max(0, score));
  const { diameter, stroke, fontSize } = SIZES[size];
  const radius = (diameter - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={diameter} height={diameter} viewBox={`0 0 ${diameter} ${diameter}`}>
        <circle cx={diameter / 2} cy={diameter / 2} r={radius} fill="none" stroke="#dbeafe" strokeWidth={stroke} />
        <circle
          cx={diameter / 2}
          cy={diameter / 2}
          r={radius}
          fill="none"
          stroke="#3b82f6"
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${diameter / 2} ${diameter / 2})`}
        />
        <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle" className={`${fontSize} font-bold fill-slate-900`}>
          {clamped}
        </text>
      </svg>
      {label && <span className="text-xs text-slate-600">{label}</span>}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run components/ScoreCircle.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd frontend && git add components/ScoreCircle.tsx components/ScoreCircle.test.tsx
git commit -m "feat: add ScoreCircle progress indicator"
```

---

### Task 7: CV file validation + `CVDropzone`

**Files:**
- Create: `frontend/lib/validation.ts`
- Create: `frontend/components/CVDropzone.tsx`
- Test: `frontend/lib/validation.test.ts`
- Test: `frontend/components/CVDropzone.test.tsx`

**Interfaces:**
- Produces: `MAX_CV_SIZE_BYTES` (`5 * 1024 * 1024`), `validateCvFile(file: File): string | null` in `lib/validation.ts` (returns a French error message, or `null` if valid)
- Produces: `CVDropzone({ file: File | null; onFileSelected: (file: File | null) => void })` in `components/CVDropzone.tsx`

- [ ] **Step 1: Write the failing validation tests**

`frontend/lib/validation.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { validateCvFile, MAX_CV_SIZE_BYTES } from "./validation";

function makeFile(name: string, size: number, type = "application/octet-stream"): File {
  return new File([new Uint8Array(size)], name, { type });
}

describe("validateCvFile", () => {
  it("accepts a valid PDF", () => {
    expect(validateCvFile(makeFile("cv.pdf", 1024))).toBeNull();
  });

  it("accepts a valid DOCX", () => {
    expect(validateCvFile(makeFile("cv.docx", 1024))).toBeNull();
  });

  it("rejects an unsupported extension", () => {
    expect(validateCvFile(makeFile("cv.txt", 1024))).toContain("PDF ou un DOCX");
  });

  it("rejects a file over the size limit", () => {
    expect(validateCvFile(makeFile("cv.pdf", MAX_CV_SIZE_BYTES + 1))).toContain("5 Mo");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run lib/validation.test.ts`
Expected: FAIL — `./validation` does not exist yet.

- [ ] **Step 3: Implement `validateCvFile`**

`frontend/lib/validation.ts`:

```ts
export const MAX_CV_SIZE_BYTES = 5 * 1024 * 1024;

const ALLOWED_EXTENSIONS = [".pdf", ".docx"];

export function validateCvFile(file: File): string | null {
  const lowerName = file.name.toLowerCase();
  const hasAllowedExtension = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
  if (!hasAllowedExtension) {
    return "Format de fichier non supporté. Utilisez un PDF ou un DOCX.";
  }
  if (file.size > MAX_CV_SIZE_BYTES) {
    return "Le fichier dépasse la taille maximale autorisée (5 Mo).";
  }
  return null;
}
```

- [ ] **Step 4: Run validation tests to verify they pass**

Run: `cd frontend && npx vitest run lib/validation.test.ts`
Expected: PASS

- [ ] **Step 5: Write the failing component tests**

`frontend/components/CVDropzone.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { CVDropzone } from "./CVDropzone";

function makeFile(name: string, type: string): File {
  return new File(["content"], name, { type });
}

describe("CVDropzone", () => {
  it("calls onFileSelected with a valid file", () => {
    const onFileSelected = vi.fn();
    render(<CVDropzone file={null} onFileSelected={onFileSelected} />);

    const input = screen.getByLabelText("Sélectionner un CV");
    const file = makeFile("cv.pdf", "application/pdf");
    fireEvent.change(input, { target: { files: [file] } });

    expect(onFileSelected).toHaveBeenCalledWith(file);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows an error and calls onFileSelected(null) for an invalid file", () => {
    const onFileSelected = vi.fn();
    render(<CVDropzone file={null} onFileSelected={onFileSelected} />);

    const input = screen.getByLabelText("Sélectionner un CV");
    const file = makeFile("cv.txt", "text/plain");
    fireEvent.change(input, { target: { files: [file] } });

    expect(onFileSelected).toHaveBeenCalledWith(null);
    expect(screen.getByRole("alert")).toHaveTextContent("PDF ou un DOCX");
  });

  it("shows the selected file's name", () => {
    const file = makeFile("mon-cv.pdf", "application/pdf");
    render(<CVDropzone file={file} onFileSelected={vi.fn()} />);
    expect(screen.getByText("mon-cv.pdf")).toBeInTheDocument();
  });
});
```

- [ ] **Step 6: Run component tests to verify they fail**

Run: `cd frontend && npx vitest run components/CVDropzone.test.tsx`
Expected: FAIL — `./CVDropzone` does not exist yet.

- [ ] **Step 7: Implement `CVDropzone`**

`frontend/components/CVDropzone.tsx`:

```tsx
"use client";

import { useRef, useState, type DragEvent, type ChangeEvent } from "react";
import { validateCvFile } from "@/lib/validation";

interface CVDropzoneProps {
  file: File | null;
  onFileSelected: (file: File | null) => void;
}

export function CVDropzone({ file, onFileSelected }: CVDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  function handleFile(candidate: File | undefined) {
    if (!candidate) return;
    const validationError = validateCvFile(candidate);
    setError(validationError);
    onFileSelected(validationError ? null : candidate);
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    handleFile(event.target.files?.[0]);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    handleFile(event.dataTransfer.files?.[0]);
  }

  return (
    <div>
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleDrop}
        className="cursor-pointer rounded-xl border-2 border-dashed border-blue-200 bg-white p-7 text-center"
      >
        <p className="text-sm font-semibold text-slate-900">
          {file ? file.name : "Glissez votre CV ici ou cliquez pour parcourir"}
        </p>
        <p className="mt-1 text-xs text-slate-500">PDF ou DOCX, 5 Mo max</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          onChange={handleInputChange}
          className="hidden"
          aria-label="Sélectionner un CV"
        />
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 8: Run component tests to verify they pass**

Run: `cd frontend && npx vitest run components/CVDropzone.test.tsx`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
cd frontend && git add lib/validation.ts lib/validation.test.ts components/CVDropzone.tsx components/CVDropzone.test.tsx
git commit -m "feat: add CV file validation and CVDropzone component"
```

---

### Task 8: `OfferInput` component

**Files:**
- Create: `frontend/components/OfferInput.tsx`
- Test: `frontend/components/OfferInput.test.tsx`

**Interfaces:**
- Produces: `OfferInputValue` (`{ mode: "text" | "url"; text: string; url: string }`), `EMPTY_OFFER_VALUE`, `OfferInput({ value: OfferInputValue; onChange: (value: OfferInputValue) => void })` in `components/OfferInput.tsx` — tabbed "Coller le texte" / "URL de l'offre" input, only one field active at a time.

- [ ] **Step 1: Write the failing tests**

`frontend/components/OfferInput.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { OfferInput, EMPTY_OFFER_VALUE } from "./OfferInput";

describe("OfferInput", () => {
  it("shows the text tab by default", () => {
    render(<OfferInput value={EMPTY_OFFER_VALUE} onChange={vi.fn()} />);
    expect(screen.getByPlaceholderText("Collez ici le texte de l'offre d'emploi")).toBeInTheDocument();
  });

  it("switches to the URL tab on click", () => {
    const onChange = vi.fn();
    render(<OfferInput value={EMPTY_OFFER_VALUE} onChange={onChange} />);

    fireEvent.click(screen.getByText("URL de l'offre"));

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_OFFER_VALUE, mode: "url" });
  });

  it("shows the URL input when mode is url", () => {
    render(<OfferInput value={{ ...EMPTY_OFFER_VALUE, mode: "url" }} onChange={vi.fn()} />);
    expect(screen.getByPlaceholderText("https://...")).toBeInTheDocument();
  });

  it("reports text changes", () => {
    const onChange = vi.fn();
    render(<OfferInput value={EMPTY_OFFER_VALUE} onChange={onChange} />);

    fireEvent.change(screen.getByPlaceholderText("Collez ici le texte de l'offre d'emploi"), {
      target: { value: "Poste de développeur" },
    });

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_OFFER_VALUE, text: "Poste de développeur" });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run components/OfferInput.test.tsx`
Expected: FAIL — `./OfferInput` does not exist yet.

- [ ] **Step 3: Implement `OfferInput`**

`frontend/components/OfferInput.tsx`:

```tsx
"use client";

export interface OfferInputValue {
  mode: "text" | "url";
  text: string;
  url: string;
}

export const EMPTY_OFFER_VALUE: OfferInputValue = { mode: "text", text: "", url: "" };

interface OfferInputProps {
  value: OfferInputValue;
  onChange: (value: OfferInputValue) => void;
}

export function OfferInput({ value, onChange }: OfferInputProps) {
  return (
    <div className="rounded-xl bg-white p-4">
      <div className="mb-3 flex gap-1 border-b border-slate-200">
        <button
          type="button"
          onClick={() => onChange({ ...value, mode: "text" })}
          className={`px-4 py-2 text-sm font-semibold ${
            value.mode === "text" ? "border-b-2 border-blue-500 text-blue-600" : "text-slate-500"
          }`}
        >
          Coller le texte
        </button>
        <button
          type="button"
          onClick={() => onChange({ ...value, mode: "url" })}
          className={`px-4 py-2 text-sm font-semibold ${
            value.mode === "url" ? "border-b-2 border-blue-500 text-blue-600" : "text-slate-500"
          }`}
        >
          URL de l'offre
        </button>
      </div>
      {value.mode === "text" ? (
        <textarea
          value={value.text}
          onChange={(event) => onChange({ ...value, text: event.target.value })}
          rows={5}
          placeholder="Collez ici le texte de l'offre d'emploi"
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      ) : (
        <input
          type="url"
          value={value.url}
          onChange={(event) => onChange({ ...value, url: event.target.value })}
          placeholder="https://..."
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run components/OfferInput.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd frontend && git add components/OfferInput.tsx components/OfferInput.test.tsx
git commit -m "feat: add OfferInput tabbed text/URL component"
```

---

### Task 9: `DiagnosticReportView` component

**Files:**
- Create: `frontend/components/DiagnosticReportView.tsx`
- Test: `frontend/components/DiagnosticReportView.test.tsx`

**Interfaces:**
- Consumes: `ScoreCircle` (Task 6), `DiagnosticReport` type (Task 3)
- Produces: `DiagnosticReportView({ report: DiagnosticReport })` in `components/DiagnosticReportView.tsx` — the central report display, shared between `/diagnostic` and the `/historique` accordion.

- [ ] **Step 1: Write the failing tests**

`frontend/components/DiagnosticReportView.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { DiagnosticReportView } from "./DiagnosticReportView";
import type { DiagnosticReport } from "@/lib/types";

const baseReport: DiagnosticReport = {
  id: 1,
  created_at: "2026-08-05T10:00:00Z",
  overall_score: 62,
  structural_score: 80,
  structural_issues: ["Mise en page 2 colonnes détectée."],
  semantic_score: 44,
  missing_keywords: ["Docker", "Kubernetes"],
  recommendations: ["Ajoutez une section Compétences plus détaillée."],
};

describe("DiagnosticReportView", () => {
  it("renders the three scores", () => {
    render(<DiagnosticReportView report={baseReport} />);
    expect(screen.getByText("62")).toBeInTheDocument();
    expect(screen.getByText("80")).toBeInTheDocument();
    expect(screen.getByText("44")).toBeInTheDocument();
  });

  it("renders structural issues", () => {
    render(<DiagnosticReportView report={baseReport} />);
    expect(screen.getByText("Mise en page 2 colonnes détectée.")).toBeInTheDocument();
  });

  it("renders missing keywords", () => {
    render(<DiagnosticReportView report={baseReport} />);
    expect(screen.getByText("Docker")).toBeInTheDocument();
    expect(screen.getByText("Kubernetes")).toBeInTheDocument();
  });

  it("renders recommendations", () => {
    render(<DiagnosticReportView report={baseReport} />);
    expect(screen.getByText("Ajoutez une section Compétences plus détaillée.")).toBeInTheDocument();
  });

  it("shows an empty-state message when there are no structural issues", () => {
    render(<DiagnosticReportView report={{ ...baseReport, structural_issues: [] }} />);
    expect(screen.getByText("Aucun problème structurel détecté.")).toBeInTheDocument();
  });

  it("shows an empty-state message when there are no missing keywords", () => {
    render(<DiagnosticReportView report={{ ...baseReport, missing_keywords: [] }} />);
    expect(screen.getByText("Aucun mot-clé manquant détecté.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run components/DiagnosticReportView.test.tsx`
Expected: FAIL — `./DiagnosticReportView` does not exist yet.

- [ ] **Step 3: Implement `DiagnosticReportView`**

`frontend/components/DiagnosticReportView.tsx`:

```tsx
import { ScoreCircle } from "./ScoreCircle";
import type { DiagnosticReport } from "@/lib/types";

export function DiagnosticReportView({ report }: { report: DiagnosticReport }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4 rounded-xl bg-white p-4 shadow-sm">
        <ScoreCircle score={report.overall_score} size="lg" />
        <div>
          <p className="text-sm font-semibold text-slate-900">Score global</p>
          <p className="text-sm text-slate-600">Encore quelques ajustements et ce CV passera mieux les filtres.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <ScoreCircle score={report.structural_score} size="sm" />
            <p className="text-sm font-semibold text-slate-900">Structure</p>
          </div>
          {report.structural_issues.length === 0 ? (
            <p className="mt-2 text-sm text-slate-600">Aucun problème structurel détecté.</p>
          ) : (
            <ul className="mt-2 list-disc pl-5 text-sm text-slate-700">
              {report.structural_issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-xl bg-white p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <ScoreCircle score={report.semantic_score} size="sm" />
            <p className="text-sm font-semibold text-slate-900">Correspondance à l'offre</p>
          </div>
          {report.missing_keywords.length === 0 ? (
            <p className="mt-2 text-sm text-slate-600">Aucun mot-clé manquant détecté.</p>
          ) : (
            <ul className="mt-2 flex flex-wrap gap-1">
              {report.missing_keywords.map((keyword) => (
                <li key={keyword} className="rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700">
                  {keyword}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {report.recommendations.length > 0 && (
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <p className="text-sm font-semibold text-slate-900">Recommandations</p>
          <ul className="mt-2 list-disc pl-5 text-sm text-slate-700">
            {report.recommendations.map((recommendation) => (
              <li key={recommendation}>{recommendation}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run components/DiagnosticReportView.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd frontend && git add components/DiagnosticReportView.tsx components/DiagnosticReportView.test.tsx
git commit -m "feat: add DiagnosticReportView component"
```

---

### Task 10: Error banner + mapping

**Files:**
- Create: `frontend/lib/errors.ts`
- Create: `frontend/components/ErrorBanner.tsx`
- Test: `frontend/lib/errors.test.ts`
- Test: `frontend/components/ErrorBanner.test.tsx`

**Interfaces:**
- Consumes: `ApiError` from `lib/api` (Task 3)
- Produces: `BannerContent` (`{ message: string; variant: "error" | "warning" }`), `toBannerContent(error: unknown): BannerContent`, `isSessionExpired(error: unknown): boolean` in `lib/errors.ts`
- Produces: `ErrorBanner({ content: BannerContent })` in `components/ErrorBanner.tsx`

- [ ] **Step 1: Write the failing mapping tests**

`frontend/lib/errors.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { toBannerContent, isSessionExpired } from "./errors";
import { ApiError } from "./api";

describe("toBannerContent", () => {
  it("maps a 429 rate-limit error to the warning variant", () => {
    const content = toBannerContent(new ApiError(429, "Limite atteinte, réessayez plus tard."));
    expect(content).toEqual({ message: "Limite atteinte, réessayez plus tard.", variant: "warning" });
  });

  it("maps a 422 error to the error variant with the backend message", () => {
    const content = toBannerContent(new ApiError(422, "Ce CV semble être une image scannée."));
    expect(content).toEqual({ message: "Ce CV semble être une image scannée.", variant: "error" });
  });

  it("maps a network failure (status 0) to a generic error message", () => {
    const content = toBannerContent(new ApiError(0, "Impossible de contacter le serveur."));
    expect(content).toEqual({ message: "Impossible de contacter le serveur.", variant: "error" });
  });

  it("maps a non-ApiError to a generic error message", () => {
    const content = toBannerContent(new Error("boom"));
    expect(content).toEqual({ message: "Une erreur est survenue.", variant: "error" });
  });
});

describe("isSessionExpired", () => {
  it("is true for a 401 ApiError", () => {
    expect(isSessionExpired(new ApiError(401, "Impossible de valider les identifiants."))).toBe(true);
  });

  it("is false for other ApiErrors", () => {
    expect(isSessionExpired(new ApiError(422, "CV invalide."))).toBe(false);
  });

  it("is false for a non-ApiError", () => {
    expect(isSessionExpired(new Error("boom"))).toBe(false);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run lib/errors.test.ts`
Expected: FAIL — `./errors` does not exist yet.

- [ ] **Step 3: Implement `toBannerContent`**

`frontend/lib/errors.ts`:

```ts
import { ApiError } from "./api";

export type BannerVariant = "error" | "warning";

export interface BannerContent {
  message: string;
  variant: BannerVariant;
}

export function toBannerContent(error: unknown): BannerContent {
  if (error instanceof ApiError) {
    return { message: error.message, variant: error.status === 429 ? "warning" : "error" };
  }
  return { message: "Une erreur est survenue.", variant: "error" };
}

export function isSessionExpired(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}
```

- [ ] **Step 4: Run mapping tests to verify they pass**

Run: `cd frontend && npx vitest run lib/errors.test.ts`
Expected: PASS

- [ ] **Step 5: Write the failing `ErrorBanner` test**

`frontend/components/ErrorBanner.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ErrorBanner } from "./ErrorBanner";

describe("ErrorBanner", () => {
  it("renders the message as an alert", () => {
    render(<ErrorBanner content={{ message: "Une erreur est survenue.", variant: "error" }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Une erreur est survenue.");
  });

  it("applies warning styling for the warning variant", () => {
    render(<ErrorBanner content={{ message: "Limite atteinte.", variant: "warning" }} />);
    expect(screen.getByRole("alert").className).toContain("orange");
  });
});
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/ErrorBanner.test.tsx`
Expected: FAIL — `./ErrorBanner` does not exist yet.

- [ ] **Step 7: Implement `ErrorBanner`**

`frontend/components/ErrorBanner.tsx`:

```tsx
import type { BannerContent } from "@/lib/errors";

export function ErrorBanner({ content }: { content: BannerContent }) {
  const styles =
    content.variant === "warning"
      ? "bg-orange-50 text-orange-800 border-orange-200"
      : "bg-red-50 text-red-700 border-red-200";
  return (
    <p role="alert" className={`rounded-md border px-3 py-2 text-sm ${styles}`}>
      {content.message}
    </p>
  );
}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/ErrorBanner.test.tsx`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
cd frontend && git add lib/errors.ts lib/errors.test.ts components/ErrorBanner.tsx components/ErrorBanner.test.tsx
git commit -m "feat: add API error-to-banner mapping and ErrorBanner component"
```

---

### Task 11: `AuthForm` component

**Files:**
- Create: `frontend/components/AuthForm.tsx`
- Test: `frontend/components/AuthForm.test.tsx`

**Interfaces:**
- Consumes: `ApiError` from `lib/api` (Task 3)
- Produces: `AuthForm({ mode: "login" | "register"; onModeChange: (mode) => void; onSubmit: (email, password) => Promise<void> })` in `components/AuthForm.tsx` — on submit-rejection, shows the error inline under the email field for `409`, otherwise as a form-level banner.

- [ ] **Step 1: Write the failing tests**

`frontend/components/AuthForm.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AuthForm } from "./AuthForm";
import { ApiError } from "@/lib/api";

describe("AuthForm", () => {
  it("renders the login heading and submit label by default", () => {
    render(<AuthForm mode="login" onModeChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByText("Connexion")).toBeInTheDocument();
    expect(screen.getByText("Se connecter")).toBeInTheDocument();
  });

  it("renders the register heading and submit label in register mode", () => {
    render(<AuthForm mode="register" onModeChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByText("Inscription")).toBeInTheDocument();
    expect(screen.getByText("Créer mon compte")).toBeInTheDocument();
  });

  it("calls onModeChange when the toggle link is clicked", () => {
    const onModeChange = vi.fn();
    render(<AuthForm mode="login" onModeChange={onModeChange} onSubmit={vi.fn()} />);
    fireEvent.click(screen.getByText("Pas de compte ? S'inscrire"));
    expect(onModeChange).toHaveBeenCalledWith("register");
  });

  it("submits the typed email and password", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<AuthForm mode="login" onModeChange={vi.fn()} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText("Mot de passe"), { target: { value: "s3cret!" } });
    fireEvent.click(screen.getByText("Se connecter"));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith("jane@example.com", "s3cret!"));
  });

  it("shows the error under the email field for a 409 conflict", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new ApiError(409, "Cet email est déjà utilisé."));
    render(<AuthForm mode="register" onModeChange={vi.fn()} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "dup@example.com" } });
    fireEvent.change(screen.getByLabelText("Mot de passe"), { target: { value: "pw" } });
    fireEvent.click(screen.getByText("Créer mon compte"));

    await waitFor(() => expect(screen.getByText("Cet email est déjà utilisé.")).toBeInTheDocument());
  });

  it("shows a form-level banner for other errors", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new ApiError(401, "Email ou mot de passe incorrect."));
    render(<AuthForm mode="login" onModeChange={vi.fn()} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText("Mot de passe"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByText("Se connecter"));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Email ou mot de passe incorrect."));
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run components/AuthForm.test.tsx`
Expected: FAIL — `./AuthForm` does not exist yet.

- [ ] **Step 3: Implement `AuthForm`**

`frontend/components/AuthForm.tsx`:

```tsx
"use client";

import { useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api";

interface AuthFormProps {
  mode: "login" | "register";
  onModeChange: (mode: "login" | "register") => void;
  onSubmit: (email: string, password: string) => Promise<void>;
}

export function AuthForm({ mode, onModeChange, onSubmit }: AuthFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setEmailError(null);
    setFormError(null);
    setIsSubmitting(true);
    try {
      await onSubmit(email, password);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setEmailError(error.message);
      } else if (error instanceof ApiError) {
        setFormError(error.message);
      } else {
        setFormError("Une erreur est survenue.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <h1 className="text-xl font-bold text-slate-900">{mode === "login" ? "Connexion" : "Inscription"}</h1>
      {formError && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {formError}
        </p>
      )}
      <label className="flex flex-col gap-1 text-sm text-slate-700">
        Email
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          className="rounded-md border border-slate-300 px-3 py-2"
        />
        {emailError && <span className="text-sm text-red-600">{emailError}</span>}
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-700">
        Mot de passe
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          className="rounded-md border border-slate-300 px-3 py-2"
        />
      </label>
      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-md bg-blue-500 px-4 py-2 font-semibold text-white disabled:opacity-50"
      >
        {mode === "login" ? "Se connecter" : "Créer mon compte"}
      </button>
      <button
        type="button"
        onClick={() => onModeChange(mode === "login" ? "register" : "login")}
        className="text-sm text-blue-600 underline"
      >
        {mode === "login" ? "Pas de compte ? S'inscrire" : "Déjà un compte ? Se connecter"}
      </button>
    </form>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run components/AuthForm.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd frontend && git add components/AuthForm.tsx components/AuthForm.test.tsx
git commit -m "feat: add AuthForm login/register component"
```

---

### Task 12: `/login` page

**Files:**
- Create: `frontend/app/login/page.tsx`

**Interfaces:**
- Consumes: `AuthForm` (Task 11), `useAuth()` (Task 4)
- Produces: the `/login` route — redirects to `/diagnostic` if already authenticated, otherwise shows `AuthForm` and calls `login`/`register` from `AuthContext` on submit.

- [ ] **Step 1: Implement the login page**

`frontend/app/login/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthForm } from "@/components/AuthForm";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const { token, isLoading, login, register } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");

  useEffect(() => {
    if (!isLoading && token) router.replace("/diagnostic");
  }, [isLoading, token, router]);

  async function handleSubmit(email: string, password: string) {
    if (mode === "login") await login(email, password);
    else await register(email, password);
    router.replace("/diagnostic");
  }

  return (
    <main className="mx-auto max-w-sm px-6 py-16">
      <AuthForm mode={mode} onModeChange={setMode} onSubmit={handleSubmit} />
    </main>
  );
}
```

- [ ] **Step 2: Verify the build compiles**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 3: Manual QA**

Run: `cd frontend && npm run dev` (with the backend running on `:8000`, per `backend/README.md`) and, in the browser:
1. Visit `http://localhost:3000/login`. Confirm the login form renders.
2. Click "Pas de compte ? S'inscrire", fill in a new email/password, submit. Confirm redirect to `/diagnostic`.
3. Log out (once Task 15 adds the nav), return to `/login`, log back in with the same credentials. Confirm redirect to `/diagnostic`.
4. Try registering the same email twice. Confirm the inline error appears under the email field.
5. Try logging in with a wrong password. Confirm the form-level banner appears.

- [ ] **Step 4: Commit**

```bash
cd frontend && git add app/login/page.tsx
git commit -m "feat: add /login page"
```

---

### Task 13: `/diagnostic` page

**Files:**
- Create: `frontend/app/diagnostic/page.tsx`

**Interfaces:**
- Consumes: `RequireAuth` (Task 5), `CVDropzone` (Task 7), `OfferInput` + `EMPTY_OFFER_VALUE` (Task 8), `DiagnosticReportView` (Task 9), `ErrorBanner` + `toBannerContent` + `isSessionExpired` (Task 10), `createDiagnostic` (Task 3), `useAuth()` (Task 4)
- Produces: the `/diagnostic` route — CV + offer form, loading state during submission, the resulting report displayed below the form, and a redirect-to-`/login` + logout on a 401 (expired session).

- [ ] **Step 1: Implement the diagnostic page**

`frontend/app/diagnostic/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import { CVDropzone } from "@/components/CVDropzone";
import { OfferInput, EMPTY_OFFER_VALUE, type OfferInputValue } from "@/components/OfferInput";
import { DiagnosticReportView } from "@/components/DiagnosticReportView";
import { ErrorBanner } from "@/components/ErrorBanner";
import { toBannerContent, isSessionExpired, type BannerContent } from "@/lib/errors";
import { createDiagnostic } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { DiagnosticReport } from "@/lib/types";

export default function DiagnosticPage() {
  return (
    <RequireAuth>
      <DiagnosticPageContent />
    </RequireAuth>
  );
}

function DiagnosticPageContent() {
  const { token, logout } = useAuth();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [offer, setOffer] = useState<OfferInputValue>(EMPTY_OFFER_VALUE);
  const [report, setReport] = useState<DiagnosticReport | null>(null);
  const [banner, setBanner] = useState<BannerContent | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canSubmit =
    Boolean(file) && (offer.mode === "text" ? offer.text.trim().length > 0 : offer.url.trim().length > 0);

  async function handleSubmit() {
    if (!token || !file) return;
    setBanner(null);
    setIsSubmitting(true);
    try {
      const result = await createDiagnostic(token, file, {
        text: offer.mode === "text" ? offer.text.trim() || undefined : undefined,
        url: offer.mode === "url" ? offer.url.trim() || undefined : undefined,
      });
      setReport(result);
    } catch (error) {
      if (isSessionExpired(error)) {
        logout();
        router.replace("/login");
        return;
      }
      setBanner(toBannerContent(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <h1 className="text-xl font-bold text-slate-900">Analyser un CV</h1>
      <p className="mt-1 text-sm text-slate-600">
        Uploadez votre CV et l&apos;offre visée pour comprendre ce qui bloque côté ATS.
      </p>

      <div className="mt-6 flex flex-col gap-4">
        <CVDropzone file={file} onFileSelected={setFile} />
        <OfferInput value={offer} onChange={setOffer} />
        {banner && <ErrorBanner content={banner} />}
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit || isSubmitting}
          className="rounded-md bg-blue-500 px-4 py-3 font-semibold text-white disabled:opacity-50"
        >
          {isSubmitting ? "Analyse en cours, ça prend quelques secondes..." : "Analyser mon CV"}
        </button>
      </div>

      {report && (
        <div className="mt-10">
          <DiagnosticReportView report={report} />
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Verify the build compiles**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 3: Manual QA**

With both servers running:
1. Visit `/diagnostic` while logged out. Confirm redirect to `/login`.
2. Log in, go to `/diagnostic`. Confirm the "Analyser mon CV" button is disabled until a valid CV file and offer text/URL are both provided.
3. Upload a real PDF or DOCX CV, paste a short offer text, submit. Confirm the loading label appears, then the report renders below the form with the three scores, issues, missing keywords, and recommendations.
4. Try uploading a `.txt` file. Confirm `CVDropzone`'s inline error appears and the submit button stays disabled.
5. Switch to the "URL de l'offre" tab, submit a URL the backend can't scrape. Confirm the 422 error banner shows the backend's fallback message.
6. Submit more than the backend's hourly rate limit (10) in a row. Confirm the 429 banner appears in the warning (orange) style.

- [ ] **Step 4: Commit**

```bash
cd frontend && git add app/diagnostic/page.tsx
git commit -m "feat: add /diagnostic page"
```

---

### Task 14: `ConfirmDialog` + `/historique` page

**Files:**
- Create: `frontend/components/ConfirmDialog.tsx`
- Test: `frontend/components/ConfirmDialog.test.tsx`
- Create: `frontend/app/historique/page.tsx`

**Interfaces:**
- Produces: `ConfirmDialog({ message: string; onConfirm: () => void; onCancel: () => void })` in `components/ConfirmDialog.tsx`
- Consumes: `RequireAuth` (Task 5), `DiagnosticReportView` (Task 9), `ErrorBanner` + `toBannerContent` + `isSessionExpired` (Task 10), `listDiagnostics` + `deleteAllDiagnostics` (Task 3), `useAuth()` (Task 4), `ConfirmDialog` (this task)
- Produces: the `/historique` route — list of past diagnostics (date + score), inline accordion expansion, a "supprimer tout mon historique" flow gated by `ConfirmDialog`, and a redirect-to-`/login` + logout on a 401 (expired session).

- [ ] **Step 1: Write the failing `ConfirmDialog` test**

`frontend/components/ConfirmDialog.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("renders the message", () => {
    render(<ConfirmDialog message="Supprimer ?" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText("Supprimer ?")).toBeInTheDocument();
  });

  it("calls onCancel when Annuler is clicked", () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog message="Supprimer ?" onConfirm={vi.fn()} onCancel={onCancel} />);
    fireEvent.click(screen.getByText("Annuler"));
    expect(onCancel).toHaveBeenCalled();
  });

  it("calls onConfirm when Supprimer is clicked", () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog message="Supprimer ?" onConfirm={onConfirm} onCancel={vi.fn()} />);
    fireEvent.click(screen.getByText("Supprimer"));
    expect(onConfirm).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/ConfirmDialog.test.tsx`
Expected: FAIL — `./ConfirmDialog` does not exist yet.

- [ ] **Step 3: Implement `ConfirmDialog`**

`frontend/components/ConfirmDialog.tsx`:

```tsx
interface ConfirmDialogProps {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ message, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-slate-900/40">
      <div className="w-full max-w-sm rounded-xl bg-white p-6">
        <p className="text-sm text-slate-800">{message}</p>
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="rounded-md px-3 py-2 text-sm text-slate-600">
            Annuler
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white"
          >
            Supprimer
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/ConfirmDialog.test.tsx`
Expected: PASS

- [ ] **Step 5: Implement the historique page**

`frontend/app/historique/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import { DiagnosticReportView } from "@/components/DiagnosticReportView";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { toBannerContent, isSessionExpired, type BannerContent } from "@/lib/errors";
import { listDiagnostics, deleteAllDiagnostics } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { DiagnosticReport } from "@/lib/types";

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
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [banner, setBanner] = useState<BannerContent | null>(null);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    listDiagnostics(token)
      .then(setDiagnostics)
      .catch((error) => {
        if (isSessionExpired(error)) {
          logout();
          router.replace("/login");
          return;
        }
        setBanner(toBannerContent(error));
      })
      .finally(() => setIsLoading(false));
  }, [token, logout, router]);

  async function handleDeleteAll() {
    if (!token) return;
    setIsConfirmOpen(false);
    try {
      await deleteAllDiagnostics(token);
      setDiagnostics([]);
    } catch (error) {
      if (isSessionExpired(error)) {
        logout();
        router.replace("/login");
        return;
      }
      setBanner(toBannerContent(error));
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900">Historique</h1>
        {diagnostics.length > 0 && (
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

      {!isLoading && diagnostics.length === 0 && (
        <p className="mt-6 text-sm text-slate-600">Aucun diagnostic pour le moment.</p>
      )}

      <ul className="mt-6 flex flex-col gap-3">
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

      {isConfirmOpen && (
        <ConfirmDialog
          message="Supprimer définitivement tout votre historique de diagnostics ? Cette action est irréversible."
          onConfirm={handleDeleteAll}
          onCancel={() => setIsConfirmOpen(false)}
        />
      )}
    </main>
  );
}
```

- [ ] **Step 6: Verify the build compiles**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 7: Manual QA**

With both servers running and at least one diagnostic already created (Task 13's manual QA):
1. Visit `/historique`. Confirm the diagnostic appears as a card with a date and score.
2. Click the card. Confirm it expands in place to show the full report, and collapses again on a second click.
3. Click "Supprimer tout mon historique". Confirm the confirmation dialog appears; click "Annuler" and confirm nothing is deleted.
4. Reopen the dialog and click "Supprimer". Confirm the list empties and the "Aucun diagnostic pour le moment." message appears.

- [ ] **Step 8: Commit**

```bash
cd frontend && git add components/ConfirmDialog.tsx components/ConfirmDialog.test.tsx app/historique/page.tsx
git commit -m "feat: add /historique page with inline accordion and purge flow"
```

---

### Task 15: `TopNav` + root page redirect + layout wiring

**Files:**
- Create: `frontend/components/TopNav.tsx`
- Test: `frontend/components/TopNav.test.tsx`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/page.test.tsx`

**Interfaces:**
- Consumes: `useAuth()` (Task 4)
- Produces: `TopNav()` in `components/TopNav.tsx` — logo-only when logged out, full nav (links + email + logout) when logged in
- Modifies: `app/page.tsx` from the Task 2 placeholder into the real `/` → `/diagnostic` or `/login` redirect

- [ ] **Step 1: Write the failing `TopNav` tests**

`frontend/components/TopNav.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { TopNav } from "./TopNav";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
  usePathname: () => "/diagnostic",
}));

const logoutMock = vi.fn();
const useAuthMock = vi.fn();
vi.mock("@/context/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

beforeEach(() => {
  replaceMock.mockReset();
  logoutMock.mockReset();
  useAuthMock.mockReset();
});

describe("TopNav", () => {
  it("shows only the logo when logged out", () => {
    useAuthMock.mockReturnValue({ user: null, logout: logoutMock });
    render(<TopNav />);
    expect(screen.getByText("📄 Diagnostic ATS")).toBeInTheDocument();
    expect(screen.queryByText("Historique")).not.toBeInTheDocument();
  });

  it("shows nav links, email, and logs out when logged in", () => {
    useAuthMock.mockReturnValue({ user: { id: 1, email: "jane@example.com" }, logout: logoutMock });
    render(<TopNav />);
    expect(screen.getByText("Historique")).toBeInTheDocument();
    expect(screen.getByText("jane@example.com")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Se déconnecter"));
    expect(logoutMock).toHaveBeenCalled();
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run components/TopNav.test.tsx`
Expected: FAIL — `./TopNav` does not exist yet.

- [ ] **Step 3: Implement `TopNav`**

`frontend/components/TopNav.tsx`:

```tsx
"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export function TopNav() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  if (!user) {
    return (
      <header className="border-b border-slate-200 bg-white px-6 py-3">
        <span className="text-base font-bold text-slate-900">📄 Diagnostic ATS</span>
      </header>
    );
  }

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
      <span className="text-base font-bold text-slate-900">📄 Diagnostic ATS</span>
      <nav className="flex items-center gap-5 text-sm text-slate-600">
        <Link href="/diagnostic" className={pathname === "/diagnostic" ? "font-semibold text-blue-600" : ""}>
          Nouveau diagnostic
        </Link>
        <Link href="/historique" className={pathname === "/historique" ? "font-semibold text-blue-600" : ""}>
          Historique
        </Link>
        <span>{user.email}</span>
        <button type="button" onClick={handleLogout} className="font-semibold text-slate-600">
          Se déconnecter
        </button>
      </nav>
    </header>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run components/TopNav.test.tsx`
Expected: PASS

- [ ] **Step 5: Wire `TopNav` into the root layout**

Modify `frontend/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import { TopNav } from "@/components/TopNav";

export const metadata: Metadata = {
  title: "Diagnostic ATS",
  description: "Comprendre pourquoi votre CV est mal traité par les ATS.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="min-h-screen bg-slate-50 text-slate-900">
        <AuthProvider>
          <TopNav />
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 6: Replace the root page's failing test with the redirect test**

Replace the contents of `frontend/app/page.test.tsx`:

```tsx
import { render, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Home from "./page";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

const useAuthMock = vi.fn();
vi.mock("@/context/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

beforeEach(() => {
  replaceMock.mockReset();
  useAuthMock.mockReset();
});

describe("Home page", () => {
  it("redirects to /diagnostic when authenticated", async () => {
    useAuthMock.mockReturnValue({ token: "abc", isLoading: false });
    render(<Home />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/diagnostic"));
  });

  it("redirects to /login when not authenticated", async () => {
    useAuthMock.mockReturnValue({ token: null, isLoading: false });
    render(<Home />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });
});
```

- [ ] **Step 7: Run test to verify it fails**

Run: `cd frontend && npx vitest run app/page.test.tsx`
Expected: FAIL — `app/page.tsx` still renders the static placeholder, `replaceMock` is never called.

- [ ] **Step 8: Replace the placeholder home page with the redirect**

`frontend/app/page.tsx`:

```tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function Home() {
  const { token, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    router.replace(token ? "/diagnostic" : "/login");
  }, [isLoading, token, router]);

  return null;
}
```

- [ ] **Step 9: Run test to verify it passes**

Run: `cd frontend && npx vitest run app/page.test.tsx`
Expected: PASS

- [ ] **Step 10: Run the full test suite and the build**

Run: `cd frontend && npx vitest run && npm run build`
Expected: PASS (all tests, production build)

- [ ] **Step 11: Manual QA**

1. Visit `/` while logged out. Confirm redirect to `/login`.
2. Log in. Confirm redirect to `/diagnostic` and the top nav now shows "Nouveau diagnostic", "Historique", the account email, and "Se déconnecter".
3. Click "Se déconnecter". Confirm redirect to `/login` and the nav collapses back to logo-only.

- [ ] **Step 12: Commit**

```bash
cd frontend && git add components/TopNav.tsx components/TopNav.test.tsx app/layout.tsx app/page.tsx app/page.test.tsx
git commit -m "feat: add TopNav and wire root page redirect"
```

---

### Task 16: Frontend README + final manual QA pass

**Files:**
- Create: `frontend/README.md`

**Interfaces:**
- None — documentation and end-to-end verification only.

- [ ] **Step 1: Write the frontend README**

`frontend/README.md`:

```markdown
# Diagnostic ATS — Frontend

## Setup

1. `npm install`
2. Copy `.env.local.example` to `.env.local` and adjust `NEXT_PUBLIC_API_URL` if the backend isn't running on `http://localhost:8000`.
3. Make sure the backend is running (see `../backend/README.md`) — CORS is already configured for `http://localhost:3000`.
4. `npm run dev`
5. Open `http://localhost:3000`.

## Tests

`npm test`

## Pages

- `/login` — sign in / register (single form, toggled mode)
- `/diagnostic` — upload a CV + job offer, see the diagnostic report
- `/historique` — past diagnostics, expandable inline, with a full-history purge option
- `/` — redirects to `/diagnostic` or `/login` depending on auth state
```

- [ ] **Step 2: Run the full test suite and build one more time**

Run: `cd frontend && npx vitest run && npm run build`
Expected: PASS

- [ ] **Step 3: Full manual QA pass**

With `backend` (`uvicorn app.main:app --reload`) and `frontend` (`npm run dev`) both running, walk through the entire flow once end-to-end:
1. Register a new account, get redirected to `/diagnostic`.
2. Upload a real CV (PDF and, separately, DOCX) with a pasted job offer. Confirm both produce a sensible report.
3. Repeat using the "URL de l'offre" tab with a real job posting URL.
4. Visit `/historique`, confirm all diagnostics from this session appear, newest first, with correct dates.
5. Expand and collapse a couple of entries.
6. Purge the history and confirm it's empty.
7. Log out and back in; confirm the session (and history) persists across reload via the stored JWT.

- [ ] **Step 4: Commit**

```bash
cd frontend && git add README.md
git commit -m "docs: add frontend README"
```
