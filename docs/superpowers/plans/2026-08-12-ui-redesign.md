# Refonte UI/UX de l'application — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the app a coherent, professional visual identity (sober amber/slate palette, sidebar navigation, shared component primitives, dark mode) across every page, without changing any existing behavior.

**Architecture:** Introduce four presentation-only primitives in `frontend/components/ui/` (`Button`, `Card`, `Badge`, `Field`), replace `TopNav` with a `Sidebar`, then restyle every existing component and page in place to use the new tokens/primitives. No API calls, state, or routing logic changes anywhere in this plan.

**Tech Stack:** Next.js 14 (App Router), React 18, Tailwind CSS 3.4, TypeScript, Vitest + Testing Library, `lucide-react` (new dependency).

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-08-12-ui-redesign-design.md` — every task implements a piece of it.
- No behavior changes: every restyled file must keep its exact props, exported names, state, handlers, and API calls. Only JSX markup/className changes.
- New dependency: `lucide-react` `^1.31.0`. No other new dependencies.
- Dark mode strategy: Tailwind `darkMode: "media"` (follows OS preference, no manual toggle in this plan).
- Color tokens (from the design spec): page bg `bg-slate-50 dark:bg-ink-950`; surface `bg-white dark:bg-ink-900`; border `border-slate-200 dark:border-ink-800`; text primary `text-slate-900 dark:text-slate-50`; text secondary `text-slate-600 dark:text-slate-400`; accent `text-amber-700 dark:text-amber-400` / `bg-amber-100 dark:bg-amber-950`; primary CTA `bg-slate-900 text-white dark:bg-slate-50 dark:text-slate-900`; danger `bg-red-600 dark:bg-red-500`; status success `emerald`, pending `amber`, failure `red`.
- **One documented exception:** `ErrorBanner`'s `warning` variant must keep the literal substring `"orange"` in its class list — `frontend/components/ErrorBanner.test.tsx:13` asserts `className.toContain("orange")`. This is the only place using `orange` instead of `amber`; every other warning/pending UI in the app uses `amber`.
- Every existing `*.test.tsx` file (except the `TopNav.test.tsx` → `Sidebar.test.tsx` rename in Task 6) keeps its assertions unchanged and must stay green after its component's restyle — none of them assert Tailwind class names except `ErrorBanner.test.tsx` (handled by the exception above).
- Run tests from `frontend/`: `npm test` (all) or `npx vitest run path/to/File.test.tsx` (single file).

---

## File Structure

New files:
- `frontend/tailwind.config.test.ts` — sanity-checks the new tokens.
- `frontend/components/ui/Button.tsx`, `Button.test.tsx`
- `frontend/components/ui/Card.tsx`, `Card.test.tsx`
- `frontend/components/ui/Badge.tsx`, `Badge.test.tsx`
- `frontend/components/ui/Field.tsx`, `Field.test.tsx` (exports `Input`, `Textarea`, `Select`)
- `frontend/components/Sidebar.tsx`, `Sidebar.test.tsx`

Deleted files:
- `frontend/components/TopNav.tsx`, `TopNav.test.tsx` (replaced by `Sidebar`)

Modified files (restyle only, logic untouched): `frontend/tailwind.config.ts`, `frontend/app/layout.tsx`, `frontend/components/ErrorBanner.tsx`, `frontend/components/ConfirmDialog.tsx`, `frontend/components/CVDropzone.tsx`, `frontend/components/ScoreCircle.tsx`, `frontend/components/DiagnosticReportView.tsx`, `frontend/components/OfferInput.tsx`, `frontend/components/PersonalizedDocumentCard.tsx`, `frontend/components/PrefilledFormReview.tsx`, `frontend/components/ApplicationCard.tsx`, `frontend/components/SearchCriteriaForm.tsx`, `frontend/components/JobListingsList.tsx`, `frontend/components/CandidateProfileForm.tsx`, `frontend/components/AuthForm.tsx`, `frontend/app/login/page.tsx`, `frontend/app/diagnostic/page.tsx`, `frontend/app/candidatures/page.tsx`, `frontend/app/historique/page.tsx`, `frontend/app/profil/page.tsx`.

---

### Task 1: Design tokens — Tailwind config

**Files:**
- Modify: `frontend/tailwind.config.ts`
- Test: `frontend/tailwind.config.test.ts` (new)

**Interfaces:**
- Produces: Tailwind color tokens `ink.800` (`#232b3a`), `ink.900` (`#131924`), `ink.950` (`#0b0f16`), available as `bg-ink-900`, `border-ink-800`, `dark:bg-ink-950`, etc. in every task from here on. `darkMode: "media"` enabled.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/tailwind.config.test.ts
import { describe, it, expect } from "vitest";
import config from "./tailwind.config";

describe("tailwind.config", () => {
  it("enables media-based dark mode", () => {
    expect(config.darkMode).toBe("media");
  });

  it("defines the ink color scale used for dark surfaces", () => {
    const colors = config.theme?.extend?.colors as Record<string, Record<string, string>> | undefined;
    expect(colors?.ink).toEqual({
      800: "#232b3a",
      900: "#131924",
      950: "#0b0f16",
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tailwind.config.test.ts`
Expected: FAIL (`darkMode` is `undefined`, `colors?.ink` is `undefined`)

- [ ] **Step 3: Write the implementation**

```ts
// frontend/tailwind.config.ts
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "media",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          800: "#232b3a",
          900: "#131924",
          950: "#0b0f16",
        },
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tailwind.config.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/tailwind.config.ts frontend/tailwind.config.test.ts
git commit -m "feat(ui): add ink color tokens and enable media dark mode"
```

---

### Task 2: `Button` primitive

**Files:**
- Create: `frontend/components/ui/Button.tsx`
- Test: `frontend/components/ui/Button.test.tsx`
- Modify: `frontend/package.json` (add `lucide-react`)

**Interfaces:**
- Consumes: none.
- Produces: `Button` component, `frontend/components/ui/Button.tsx`, props `{ variant?: "primary" | "secondary" | "danger"; size?: "sm" | "md"; isLoading?: boolean } & ButtonHTMLAttributes<HTMLButtonElement>`. Defaults: `variant="primary"`, `size="md"`, `isLoading=false`. When `isLoading` is true, the button is disabled and shows a spinning `Loader2` icon before its children. `disabled` prop and `isLoading` are OR'd together for the final disabled state.

- [ ] **Step 1: Install the dependency**

```bash
cd frontend && npm install lucide-react@^1.31.0
```

- [ ] **Step 2: Write the failing test**

```tsx
// frontend/components/ui/Button.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Button } from "./Button";

describe("Button", () => {
  it("renders its children", () => {
    render(<Button>Valider</Button>);
    expect(screen.getByRole("button", { name: "Valider" })).toBeInTheDocument();
  });

  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Valider</Button>);
    fireEvent.click(screen.getByRole("button", { name: "Valider" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("is disabled when the disabled prop is set", () => {
    render(<Button disabled>Valider</Button>);
    expect(screen.getByRole("button", { name: "Valider" })).toBeDisabled();
  });

  it("disables the button and blocks onClick when isLoading is true", () => {
    const onClick = vi.fn();
    render(
      <Button isLoading onClick={onClick}>
        Envoi en cours...
      </Button>
    );
    const button = screen.getByRole("button", { name: "Envoi en cours..." });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("applies the danger variant class", () => {
    render(<Button variant="danger">Supprimer</Button>);
    expect(screen.getByRole("button", { name: "Supprimer" }).className).toContain("bg-red-600");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/ui/Button.test.tsx`
Expected: FAIL (`./Button` does not exist)

- [ ] **Step 4: Write the implementation**

```tsx
// frontend/components/ui/Button.tsx
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";

export type ButtonVariant = "primary" | "secondary" | "danger";
export type ButtonSize = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "bg-slate-900 text-white hover:bg-slate-800 dark:bg-slate-50 dark:text-slate-900 dark:hover:bg-slate-200",
  secondary:
    "border border-slate-300 text-slate-700 hover:bg-slate-50 dark:border-ink-800 dark:text-slate-300 dark:hover:bg-ink-900",
  danger: "bg-red-600 text-white hover:bg-red-700 dark:bg-red-500 dark:hover:bg-red-600",
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", isLoading = false, disabled, className = "", children, type, ...props }, ref) => {
    return (
      <button
        ref={ref}
        type={type ?? "button"}
        disabled={disabled || isLoading}
        className={`inline-flex items-center justify-center gap-2 rounded-full font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
        {...props}
      >
        {isLoading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/ui/Button.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/components/ui/Button.tsx frontend/components/ui/Button.test.tsx
git commit -m "feat(ui): add Button primitive with lucide-react loading spinner"
```

---

### Task 3: `Card` primitive

**Files:**
- Create: `frontend/components/ui/Card.tsx`
- Test: `frontend/components/ui/Card.test.tsx`

**Interfaces:**
- Consumes: none.
- Produces: `Card` component, `frontend/components/ui/Card.tsx`, props `HTMLAttributes<HTMLDivElement>` (renders a `<div>`, forwards all props including `className` and `data-testid`). Default classes: `rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-ink-800 dark:bg-ink-900`. No default padding — callers add `p-4`/`p-6` etc. via `className`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/components/ui/Card.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Card } from "./Card";

describe("Card", () => {
  it("renders its children", () => {
    render(<Card>Contenu</Card>);
    expect(screen.getByText("Contenu")).toBeInTheDocument();
  });

  it("applies the default surface classes", () => {
    render(<Card data-testid="card">Contenu</Card>);
    expect(screen.getByTestId("card").className).toContain("rounded-2xl");
  });

  it("merges a custom className with the defaults", () => {
    render(
      <Card data-testid="card" className="p-4">
        Contenu
      </Card>
    );
    const className = screen.getByTestId("card").className;
    expect(className).toContain("rounded-2xl");
    expect(className).toContain("p-4");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/ui/Card.test.tsx`
Expected: FAIL (`./Card` does not exist)

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/components/ui/Card.tsx
import type { HTMLAttributes } from "react";

export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-ink-800 dark:bg-ink-900 ${className}`}
      {...props}
    />
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/ui/Card.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/Card.tsx frontend/components/ui/Card.test.tsx
git commit -m "feat(ui): add Card primitive"
```

---

### Task 4: `Badge` primitive

**Files:**
- Create: `frontend/components/ui/Badge.tsx`
- Test: `frontend/components/ui/Badge.test.tsx`

**Interfaces:**
- Consumes: none.
- Produces: `Badge` component + `BadgeVariant` type, `frontend/components/ui/Badge.tsx`, props `{ variant?: "neutral" | "amber" | "emerald" | "red" } & HTMLAttributes<HTMLSpanElement>` (renders a `<span>`). Default variant: `"neutral"`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/components/ui/Badge.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("renders its children", () => {
    render(<Badge>Envoyée</Badge>);
    expect(screen.getByText("Envoyée")).toBeInTheDocument();
  });

  it("defaults to the neutral variant", () => {
    render(<Badge>Envoyée</Badge>);
    expect(screen.getByText("Envoyée").className).toContain("bg-slate-100");
  });

  it("applies the emerald variant class", () => {
    render(<Badge variant="emerald">Envoyée</Badge>);
    expect(screen.getByText("Envoyée").className).toContain("emerald");
  });

  it("applies the red variant class", () => {
    render(<Badge variant="red">Échec</Badge>);
    expect(screen.getByText("Échec").className).toContain("red");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/ui/Badge.test.tsx`
Expected: FAIL (`./Badge` does not exist)

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/components/ui/Badge.tsx
import type { HTMLAttributes } from "react";

export type BadgeVariant = "neutral" | "amber" | "emerald" | "red";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  neutral: "bg-slate-100 text-slate-700 dark:bg-ink-800 dark:text-slate-300",
  amber: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400",
  emerald: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400",
  red: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
};

export function Badge({ variant = "neutral", className = "", ...props }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${VARIANT_CLASSES[variant]} ${className}`}
      {...props}
    />
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/ui/Badge.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/Badge.tsx frontend/components/ui/Badge.test.tsx
git commit -m "feat(ui): add Badge primitive"
```

---

### Task 5: `Field` primitives (`Input`, `Textarea`, `Select`)

**Files:**
- Create: `frontend/components/ui/Field.tsx`
- Test: `frontend/components/ui/Field.test.tsx`

**Interfaces:**
- Consumes: none.
- Produces: `Input` (`InputHTMLAttributes<HTMLInputElement>`), `Textarea` (`TextareaHTMLAttributes<HTMLTextAreaElement>`), `Select` (`SelectHTMLAttributes<HTMLSelectElement>`), all from `frontend/components/ui/Field.tsx`. Each forwards its ref and all native props (`value`, `onChange`, `placeholder`, `required`, `rows`, `aria-label`, `children` for `Select`'s `<option>`s, etc.) and applies the same base visual classes.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/components/ui/Field.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Input, Textarea, Select } from "./Field";

describe("Input", () => {
  it("renders with its value and reports changes", () => {
    const onChange = vi.fn();
    render(<Input aria-label="Email" value="jane@example.com" onChange={onChange} />);
    const input = screen.getByLabelText("Email");
    expect(input).toHaveValue("jane@example.com");
    fireEvent.change(input, { target: { value: "new@example.com" } });
    expect(onChange).toHaveBeenCalled();
  });
});

describe("Textarea", () => {
  it("renders with its value and reports changes", () => {
    const onChange = vi.fn();
    render(<Textarea aria-label="Description" value="texte" onChange={onChange} />);
    const textarea = screen.getByLabelText("Description");
    expect(textarea).toHaveValue("texte");
    fireEvent.change(textarea, { target: { value: "nouveau texte" } });
    expect(onChange).toHaveBeenCalled();
  });
});

describe("Select", () => {
  it("renders its options and reports changes", () => {
    const onChange = vi.fn();
    render(
      <Select aria-label="Type" value="a" onChange={onChange}>
        <option value="a">A</option>
        <option value="b">B</option>
      </Select>
    );
    const select = screen.getByLabelText("Type");
    expect(select).toHaveValue("a");
    fireEvent.change(select, { target: { value: "b" } });
    expect(onChange).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/ui/Field.test.tsx`
Expected: FAIL (`./Field` does not exist)

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/components/ui/Field.tsx
import { forwardRef, type InputHTMLAttributes, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

const fieldClassName =
  "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none dark:border-ink-800 dark:bg-ink-900 dark:text-slate-50 dark:placeholder:text-slate-500 dark:focus:border-slate-50";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className = "", ...props }, ref) => <input ref={ref} className={`${fieldClassName} ${className}`} {...props} />
);
Input.displayName = "Input";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className = "", ...props }, ref) => (
    <textarea ref={ref} className={`${fieldClassName} ${className}`} {...props} />
  )
);
Textarea.displayName = "Textarea";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className = "", ...props }, ref) => <select ref={ref} className={`${fieldClassName} ${className}`} {...props} />
);
Select.displayName = "Select";
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/ui/Field.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/Field.tsx frontend/components/ui/Field.test.tsx
git commit -m "feat(ui): add Input/Textarea/Select field primitives"
```

---

### Task 6: `Sidebar` shell (replaces `TopNav`)

**Files:**
- Create: `frontend/components/Sidebar.tsx`
- Create: `frontend/components/Sidebar.test.tsx`
- Delete: `frontend/components/TopNav.tsx`, `frontend/components/TopNav.test.tsx`
- Modify: `frontend/app/layout.tsx`

**Interfaces:**
- Consumes: `useAuth()` from `@/context/AuthContext` (unchanged, returns `{ user, logout, ... }`).
- Produces: `Sidebar` component, `frontend/components/Sidebar.tsx`, no props. Renders a fixed-width vertical nav (`<aside>`), used once in `app/layout.tsx`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/components/Sidebar.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { Sidebar } from "./Sidebar";

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

describe("Sidebar", () => {
  it("shows only the brand when logged out", () => {
    useAuthMock.mockReturnValue({ user: null, logout: logoutMock });
    render(<Sidebar />);
    expect(screen.getByText("Diagnostic ATS")).toBeInTheDocument();
    expect(screen.queryByText("Historique")).not.toBeInTheDocument();
  });

  it("shows nav links, email, and logs out when logged in", () => {
    useAuthMock.mockReturnValue({ user: { id: 1, email: "jane@example.com" }, logout: logoutMock });
    render(<Sidebar />);
    expect(screen.getByText("Historique")).toBeInTheDocument();
    expect(screen.getByText("Candidatures")).toBeInTheDocument();
    expect(screen.getByText("Profil")).toBeInTheDocument();
    expect(screen.getByText("jane@example.com")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Se déconnecter"));
    expect(logoutMock).toHaveBeenCalled();
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/Sidebar.test.tsx`
Expected: FAIL (`./Sidebar` does not exist)

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/components/Sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FileSearch, Send, History, User, LogOut, FileText } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const NAV_ITEMS = [
  { href: "/diagnostic", label: "Diagnostic", icon: FileSearch },
  { href: "/candidatures", label: "Candidatures", icon: Send },
  { href: "/historique", label: "Historique", icon: History },
  { href: "/profil", label: "Profil", icon: User },
] as const;

export function Sidebar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <aside className="flex w-56 flex-shrink-0 flex-col border-r border-slate-200 bg-white px-3 py-4 dark:border-ink-800 dark:bg-ink-900">
      <Link
        href="/"
        className="mb-6 flex items-center gap-2 px-2 text-sm font-extrabold tracking-tight text-slate-900 dark:text-slate-50"
      >
        <FileText className="h-5 w-5 text-amber-600 dark:text-amber-400" aria-hidden="true" />
        Diagnostic ATS
      </Link>

      {user && (
        <>
          <nav className="flex flex-col gap-1">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
              const isActive = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-semibold transition-colors ${
                    isActive
                      ? "bg-slate-900 text-white dark:bg-slate-50 dark:text-slate-900"
                      : "text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-ink-800"
                  }`}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {label}
                </Link>
              );
            })}
          </nav>

          <div className="mt-auto flex flex-col gap-2 border-t border-slate-200 pt-3 text-xs dark:border-ink-800">
            <span className="truncate px-2.5 text-slate-500 dark:text-slate-400">{user.email}</span>
            <button
              type="button"
              onClick={handleLogout}
              className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm font-semibold text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-ink-800"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Se déconnecter
            </button>
          </div>
        </>
      )}
    </aside>
  );
}
```

```tsx
// frontend/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Diagnostic ATS",
  description: "Comprendre pourquoi votre CV est mal traité par les ATS.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="bg-slate-50 text-slate-900 dark:bg-ink-950 dark:text-slate-50">
        <AuthProvider>
          <div className="flex min-h-screen">
            <Sidebar />
            <div className="min-w-0 flex-1">{children}</div>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
```

Delete the old files:

```bash
rm frontend/components/TopNav.tsx frontend/components/TopNav.test.tsx
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/Sidebar.test.tsx`
Expected: PASS

- [ ] **Step 5: Run the full test suite to confirm nothing else references `TopNav`**

Run: `cd frontend && npm test`
Expected: PASS (no failures, no leftover import of `TopNav`)

- [ ] **Step 6: Commit**

```bash
git add -A frontend/components/Sidebar.tsx frontend/components/Sidebar.test.tsx frontend/app/layout.tsx
git rm frontend/components/TopNav.tsx frontend/components/TopNav.test.tsx
git commit -m "feat(ui): replace TopNav with a vertical Sidebar"
```

---

### Task 7: `ErrorBanner` & `ConfirmDialog`

**Files:**
- Modify: `frontend/components/ErrorBanner.tsx`
- Modify: `frontend/components/ConfirmDialog.tsx`

**Interfaces:**
- Consumes: `Button` (Task 2, `variant="secondary"|"danger"`, `size="sm"`), `Card` (Task 3).
- Produces: no change to either component's public props.

- [ ] **Step 1: Run the existing tests to confirm the baseline is green**

Run: `cd frontend && npx vitest run components/ErrorBanner.test.tsx components/ConfirmDialog.test.tsx`
Expected: PASS

- [ ] **Step 2: Restyle `ErrorBanner`**

```tsx
// frontend/components/ErrorBanner.tsx
import type { BannerContent } from "@/lib/errors";

export function ErrorBanner({ content }: { content: BannerContent }) {
  // NOTE: the warning variant keeps the literal "orange" Tailwind color
  // (not "amber") because ErrorBanner.test.tsx:13 asserts
  // `className.toContain("orange")`. Every other warning/pending UI in
  // the app uses amber — this is the one intentional exception.
  const styles =
    content.variant === "warning"
      ? "border-orange-200 bg-orange-50 text-orange-800 dark:border-orange-900 dark:bg-orange-950 dark:text-orange-300"
      : "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300";
  return (
    <p role="alert" className={`rounded-lg border px-3 py-2 text-sm ${styles}`}>
      {content.message}
    </p>
  );
}
```

- [ ] **Step 3: Restyle `ConfirmDialog`**

```tsx
// frontend/components/ConfirmDialog.tsx
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";

interface ConfirmDialogProps {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ message, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-slate-900/40">
      <Card className="w-full max-w-sm p-6">
        <p className="text-sm text-slate-800 dark:text-slate-100">{message}</p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onCancel}>
            Annuler
          </Button>
          <Button variant="danger" size="sm" onClick={onConfirm}>
            Supprimer
          </Button>
        </div>
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: Run the tests again to confirm no regressions**

Run: `cd frontend && npx vitest run components/ErrorBanner.test.tsx components/ConfirmDialog.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ErrorBanner.tsx frontend/components/ConfirmDialog.tsx
git commit -m "style: restyle ErrorBanner and ConfirmDialog with design tokens"
```

---

### Task 8: `CVDropzone`

**Files:**
- Modify: `frontend/components/CVDropzone.tsx`

**Interfaces:**
- Consumes: `lucide-react`'s `Upload` icon.
- Produces: no change to public props.

- [ ] **Step 1: Run the existing test to confirm the baseline is green**

Run: `cd frontend && npx vitest run components/CVDropzone.test.tsx`
Expected: PASS

- [ ] **Step 2: Restyle**

```tsx
// frontend/components/CVDropzone.tsx
"use client";

import { useRef, useState, type DragEvent, type ChangeEvent } from "react";
import { Upload } from "lucide-react";
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
        className="cursor-pointer rounded-xl border-2 border-dashed border-slate-300 bg-white p-7 text-center transition-colors hover:border-amber-400 dark:border-ink-800 dark:bg-ink-900 dark:hover:border-amber-500"
      >
        <Upload className="mx-auto h-6 w-6 text-slate-400 dark:text-slate-500" aria-hidden="true" />
        <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-slate-50">
          {file ? file.name : "Glissez votre CV ici ou cliquez pour parcourir"}
        </p>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">PDF ou DOCX, 5 Mo max</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          onChange={handleInputChange}
          className="sr-only"
          aria-label="Sélectionner un CV"
        />
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Run the test again to confirm no regressions**

Run: `cd frontend && npx vitest run components/CVDropzone.test.tsx`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/components/CVDropzone.tsx
git commit -m "style: restyle CVDropzone with design tokens"
```

---

### Task 9: `ScoreCircle`

**Files:**
- Modify: `frontend/components/ScoreCircle.tsx`

**Interfaces:**
- Consumes: none.
- Produces: no change to public props (`score`, `size`, `label`).

- [ ] **Step 1: Run the existing test to confirm the baseline is green**

Run: `cd frontend && npx vitest run components/ScoreCircle.test.tsx`
Expected: PASS

- [ ] **Step 2: Restyle**

```tsx
// frontend/components/ScoreCircle.tsx
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
        <circle
          cx={diameter / 2}
          cy={diameter / 2}
          r={radius}
          fill="none"
          className="stroke-slate-200 dark:stroke-ink-800"
          strokeWidth={stroke}
        />
        <circle
          cx={diameter / 2}
          cy={diameter / 2}
          r={radius}
          fill="none"
          className="stroke-amber-500 dark:stroke-amber-400"
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${diameter / 2} ${diameter / 2})`}
        />
        <text
          x="50%"
          y="50%"
          textAnchor="middle"
          dominantBaseline="middle"
          className={`${fontSize} font-bold fill-slate-900 dark:fill-slate-50`}
        >
          {clamped}
        </text>
      </svg>
      {label && <span className="text-xs text-slate-600 dark:text-slate-400">{label}</span>}
    </div>
  );
}
```

- [ ] **Step 3: Run the test again to confirm no regressions**

Run: `cd frontend && npx vitest run components/ScoreCircle.test.tsx`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/components/ScoreCircle.tsx
git commit -m "style: restyle ScoreCircle ring to the amber accent"
```

---

### Task 10: `DiagnosticReportView`

**Files:**
- Modify: `frontend/components/DiagnosticReportView.tsx`

**Interfaces:**
- Consumes: `Card` (Task 3), `Badge` (Task 4, `variant="amber"`), `ScoreCircle` (Task 9, unchanged props).
- Produces: no change to public props.

- [ ] **Step 1: Run the existing test to confirm the baseline is green**

Run: `cd frontend && npx vitest run components/DiagnosticReportView.test.tsx`
Expected: PASS

- [ ] **Step 2: Restyle**

```tsx
// frontend/components/DiagnosticReportView.tsx
import { ScoreCircle } from "./ScoreCircle";
import { Card } from "./ui/Card";
import { Badge } from "./ui/Badge";
import type { DiagnosticReport } from "@/lib/types";

export function DiagnosticReportView({ report }: { report: DiagnosticReport }) {
  return (
    <div className="flex flex-col gap-4">
      <Card className="flex items-center gap-4 p-4">
        <ScoreCircle score={report.overall_score} size="lg" />
        <div>
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">Score global</p>
          <p className="text-sm text-slate-600 dark:text-slate-400">
            Encore quelques ajustements et ce CV passera mieux les filtres.
          </p>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <ScoreCircle score={report.structural_score} size="sm" />
            <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">Structure</p>
          </div>
          {report.structural_issues.length === 0 ? (
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">Aucun problème structurel détecté.</p>
          ) : (
            <ul className="mt-2 list-disc pl-5 text-sm text-slate-700 dark:text-slate-300">
              {report.structural_issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <ScoreCircle score={report.semantic_score} size="sm" />
            <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">Correspondance à l'offre</p>
          </div>
          {report.missing_keywords.length === 0 ? (
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">Aucun mot-clé manquant détecté.</p>
          ) : (
            <ul className="mt-2 flex flex-wrap gap-1">
              {report.missing_keywords.map((keyword) => (
                <li key={keyword}>
                  <Badge variant="amber">{keyword}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {report.recommendations.length > 0 && (
        <Card className="p-4">
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">Recommandations</p>
          <ul className="mt-2 list-disc pl-5 text-sm text-slate-700 dark:text-slate-300">
            {report.recommendations.map((recommendation) => (
              <li key={recommendation}>{recommendation}</li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Run the test again to confirm no regressions**

Run: `cd frontend && npx vitest run components/DiagnosticReportView.test.tsx`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/components/DiagnosticReportView.tsx
git commit -m "style: restyle DiagnosticReportView with Card and Badge"
```

---

### Task 11: `OfferInput`

**Files:**
- Modify: `frontend/components/OfferInput.tsx`

**Interfaces:**
- Consumes: `Card` (Task 3), `Input`/`Textarea` (Task 5).
- Produces: no change to public props (`OfferInputValue`, `EMPTY_OFFER_VALUE`, `value`/`onChange`).

- [ ] **Step 1: Run the existing test to confirm the baseline is green**

Run: `cd frontend && npx vitest run components/OfferInput.test.tsx`
Expected: PASS

- [ ] **Step 2: Restyle**

```tsx
// frontend/components/OfferInput.tsx
"use client";

import { Card } from "./ui/Card";
import { Input, Textarea } from "./ui/Field";

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
    <Card className="p-4">
      <div className="mb-3 flex gap-1 border-b border-slate-200 dark:border-ink-800">
        <button
          type="button"
          onClick={() => onChange({ ...value, mode: "text" })}
          className={`px-4 py-2 text-sm font-semibold ${
            value.mode === "text"
              ? "border-b-2 border-amber-500 text-amber-700 dark:border-amber-400 dark:text-amber-400"
              : "text-slate-500 dark:text-slate-400"
          }`}
        >
          Coller le texte
        </button>
        <button
          type="button"
          onClick={() => onChange({ ...value, mode: "url" })}
          className={`px-4 py-2 text-sm font-semibold ${
            value.mode === "url"
              ? "border-b-2 border-amber-500 text-amber-700 dark:border-amber-400 dark:text-amber-400"
              : "text-slate-500 dark:text-slate-400"
          }`}
        >
          URL de l'offre
        </button>
      </div>
      {value.mode === "text" ? (
        <Textarea
          value={value.text}
          onChange={(event) => onChange({ ...value, text: event.target.value })}
          rows={5}
          placeholder="Collez ici le texte de l'offre d'emploi"
          className="w-full"
        />
      ) : (
        <Input
          type="url"
          value={value.url}
          onChange={(event) => onChange({ ...value, url: event.target.value })}
          placeholder="https://..."
          className="w-full"
        />
      )}
    </Card>
  );
}
```

- [ ] **Step 3: Run the test again to confirm no regressions**

Run: `cd frontend && npx vitest run components/OfferInput.test.tsx`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/components/OfferInput.tsx
git commit -m "style: restyle OfferInput with Card and Field primitives"
```

---

### Task 12: `PersonalizedDocumentCard`

**Files:**
- Modify: `frontend/components/PersonalizedDocumentCard.tsx`

**Interfaces:**
- Consumes: `Card` (Task 3), `Button` (Task 2, `isLoading` prop for generate/regenerate).
- Produces: no change to public props.

- [ ] **Step 1: Run the existing test to confirm the baseline is green**

Run: `cd frontend && npx vitest run components/PersonalizedDocumentCard.test.tsx`
Expected: PASS

- [ ] **Step 2: Restyle**

```tsx
// frontend/components/PersonalizedDocumentCard.tsx
"use client";

import { useState } from "react";
import { ErrorBanner } from "./ErrorBanner";
import { Card } from "./ui/Card";
import { Button } from "./ui/Button";
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
    <Card className="p-4">
      <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">{title}</p>

      {banner && (
        <div className="mt-2">
          <ErrorBanner content={banner} />
        </div>
      )}

      {!generatedDocument && (
        <Button onClick={handleGenerate} isLoading={isGenerating} size="sm" className="mt-2">
          {isGenerating ? "Génération en cours..." : generatedLabel}
        </Button>
      )}

      {generatedDocument && (
        <div className="mt-2 flex flex-col gap-2">
          <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
            Relisez ce document avant de l&apos;envoyer.
          </p>
          {generatedDocument.needs_review && (
            <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
              À vérifier : ce document pourrait contenir des éléments absents de votre CV d&apos;origine.
            </p>
          )}
          <div className="flex gap-2">
            <Button onClick={handleDownload} size="sm">
              Télécharger
            </Button>
            <Button onClick={handleGenerate} isLoading={isGenerating} variant="secondary" size="sm">
              {isGenerating ? "Génération en cours..." : "Régénérer"}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
```

- [ ] **Step 3: Run the test again to confirm no regressions**

Run: `cd frontend && npx vitest run components/PersonalizedDocumentCard.test.tsx`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/components/PersonalizedDocumentCard.tsx
git commit -m "style: restyle PersonalizedDocumentCard with Card and Button"
```

---

### Task 13: `PrefilledFormReview`

**Files:**
- Modify: `frontend/components/PrefilledFormReview.tsx`

**Interfaces:**
- Consumes: `Button` (Task 2), `Input`/`Select`/`Textarea` (Task 5).
- Produces: no change to public props.

- [ ] **Step 1: Run the existing test to confirm the baseline is green**

Run: `cd frontend && npx vitest run components/PrefilledFormReview.test.tsx`
Expected: PASS

- [ ] **Step 2: Restyle**

Note: this component keeps a plain `div` (not `Card`) for its amber-tinted wrapper, because it needs `border-amber-*`/`bg-amber-*` instead of `Card`'s default `border-slate-*`/`bg-white` — passing an overriding `className` to `Card` is not reliable since Tailwind's cascade order (not attribute order) decides which of two same-specificity utility classes wins.

```tsx
// frontend/components/PrefilledFormReview.tsx
"use client";

import { useState } from "react";
import { Button } from "./ui/Button";
import { Input, Select, Textarea } from "./ui/Field";
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
    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950">
      <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">
        Relisez et complétez le formulaire avant l&apos;envoi
      </p>
      <div className="mt-3 flex flex-col gap-3">
        {values.map((field) => {
          const needsCompletion = field.required && !field.value;
          return (
            <label key={field.name} className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-300">
              <span>
                {field.label}
                {field.is_custom && (
                  <span className="ml-2 text-xs text-amber-700 dark:text-amber-400">
                    (généré par l&apos;IA — à vérifier)
                  </span>
                )}
                {needsCompletion && (
                  <span className="ml-2 text-xs font-semibold text-red-600 dark:text-red-400">(à compléter)</span>
                )}
              </span>
              {field.field_type === "textarea" ? (
                <Textarea
                  value={field.value ?? ""}
                  onChange={(event) => updateValue(field.name, event.target.value)}
                  rows={3}
                />
              ) : field.field_type === "select" ? (
                <Select value={field.value ?? ""} onChange={(event) => updateValue(field.name, event.target.value)}>
                  <option value="" disabled hidden>
                    Sélectionnez…
                  </option>
                  {(field.options ?? []).map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </Select>
              ) : (
                <Input
                  type="text"
                  value={field.value ?? ""}
                  onChange={(event) => updateValue(field.name, event.target.value)}
                />
              )}
            </label>
          );
        })}
      </div>
      <div className="mt-4 flex gap-2">
        <Button onClick={() => onConfirm(values)} isLoading={isConfirming} size="sm">
          {isConfirming ? "Envoi en cours..." : "Envoyer la candidature"}
        </Button>
        <Button onClick={onCancel} variant="secondary" size="sm">
          Annuler
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Run the test again to confirm no regressions**

Run: `cd frontend && npx vitest run components/PrefilledFormReview.test.tsx`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/components/PrefilledFormReview.tsx
git commit -m "style: restyle PrefilledFormReview with Field and Button primitives"
```

---

### Task 14: `ApplicationCard`

**Files:**
- Modify: `frontend/components/ApplicationCard.tsx`

**Interfaces:**
- Consumes: `Card` (Task 3), `Button` (Task 2), `Badge`/`BadgeVariant` (Task 4).
- Produces: no change to public props.

- [ ] **Step 1: Run the existing test to confirm the baseline is green**

Run: `cd frontend && npx vitest run components/ApplicationCard.test.tsx`
Expected: PASS

- [ ] **Step 2: Restyle**

```tsx
// frontend/components/ApplicationCard.tsx
"use client";

import { useState } from "react";
import { DiagnosticReportView } from "./DiagnosticReportView";
import { PersonalizedDocumentCard } from "./PersonalizedDocumentCard";
import { PrefilledFormReview } from "./PrefilledFormReview";
import { ErrorBanner } from "./ErrorBanner";
import { Card } from "./ui/Card";
import { Button } from "./ui/Button";
import { Badge, type BadgeVariant } from "./ui/Badge";
import { toBannerContent, type BannerContent } from "@/lib/errors";
import {
  generateCv,
  generateLetter,
  downloadCv,
  downloadLetter,
  getPrefilledForm,
  confirmApplication,
  markApplicationSentManually,
  ApiError,
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

const STATUS_VARIANTS: Record<Application["status"], BadgeVariant> = {
  en_cours: "amber",
  soumise_auto: "emerald",
  a_soumettre_manuellement: "amber",
  soumise_manuelle_confirmee: "emerald",
  echec_soumission: "red",
};

// Verbatim match to the detail string raised by POST /applications/{id}/confirm
// (backend/app/routers/applications.py) when the candidate's CV is flagged
// needs_review by the anti-hallucination check. Matched by exact message, not
// just status 422, since other 422s (e.g. missing fields) must fall through
// to the generic error banner instead of this dedicated block.
const NEEDS_REVIEW_DETAIL =
  "Ce CV contient des éléments à vérifier avant l'envoi automatique — relisez-le ou régénérez-le depuis le diagnostic.";

export function ApplicationCard({ application, token, onUpdated }: ApplicationCardProps) {
  const [banner, setBanner] = useState<BannerContent | null>(null);
  const [isLoadingForm, setIsLoadingForm] = useState(false);
  const [prefilledFields, setPrefilledFields] = useState<FormField[] | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const [needsReviewBlock, setNeedsReviewBlock] = useState<{ fields?: FormField[] } | null>(null);
  const [acknowledgedRisk, setAcknowledgedRisk] = useState(false);

  async function submitConfirm(fields: FormField[] | undefined, overrideNeedsReview: boolean) {
    setBanner(null);
    setIsConfirming(true);
    try {
      const updated = await confirmApplication(token, application.id, fields, overrideNeedsReview);
      setPrefilledFields(null);
      setNeedsReviewBlock(null);
      setAcknowledgedRisk(false);
      onUpdated(updated);
    } catch (error) {
      if (error instanceof ApiError && error.status === 422 && error.message === NEEDS_REVIEW_DETAIL) {
        setNeedsReviewBlock({ fields });
        setAcknowledgedRisk(false);
      } else {
        setBanner(toBannerContent(error));
      }
    } finally {
      setIsConfirming(false);
    }
  }

  async function handleConfirmClick() {
    setBanner(null);
    if (application.ats_type === null) {
      await submitConfirm(undefined, false);
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
    await submitConfirm(fields, false);
  }

  function handleCancelNeedsReview() {
    setNeedsReviewBlock(null);
    setAcknowledgedRisk(false);
  }

  async function handleSendAnyway() {
    await submitConfirm(needsReviewBlock?.fields, true);
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
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">{application.job_title}</p>
          <p className="text-sm text-slate-600 dark:text-slate-400">{application.company_name}</p>
        </div>
        <Badge variant={STATUS_VARIANTS[application.status]}>{STATUS_LABELS[application.status]}</Badge>
      </div>

      {banner && (
        <div className="mt-3">
          <ErrorBanner content={banner} />
        </div>
      )}
      {application.error_message && (
        <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
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

      {needsReviewBlock && (
        <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 px-3 py-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
          <p>{NEEDS_REVIEW_DETAIL}</p>
          <label className="mt-3 flex items-start gap-2">
            <input
              type="checkbox"
              checked={acknowledgedRisk}
              onChange={(event) => setAcknowledgedRisk(event.target.checked)}
              className="mt-0.5"
            />
            <span>Je comprends le risque et je souhaite envoyer la candidature malgré tout.</span>
          </label>
          <div className="mt-3 flex gap-2">
            <Button
              variant="danger"
              size="sm"
              onClick={handleSendAnyway}
              disabled={!acknowledgedRisk}
              isLoading={isConfirming}
            >
              {isConfirming ? "Envoi en cours..." : "Envoyer quand même"}
            </Button>
            <Button variant="secondary" size="sm" onClick={handleCancelNeedsReview}>
              Annuler
            </Button>
          </div>
        </div>
      )}

      {!needsReviewBlock &&
        (application.status === "en_cours" || application.status === "echec_soumission") &&
        !prefilledFields && (
          <Button onClick={handleConfirmClick} isLoading={isLoadingForm} size="sm" className="mt-4">
            {isLoadingForm
              ? "Préparation du formulaire..."
              : application.status === "echec_soumission"
                ? "Réessayer l'envoi"
                : "Confirmer la candidature"}
          </Button>
        )}

      {!needsReviewBlock && prefilledFields && (
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
            className="w-fit text-sm font-semibold text-amber-700 underline dark:text-amber-400"
          >
            Ouvrir la page de candidature
          </a>
          <Button variant="secondary" size="sm" onClick={handleMarkSent} className="w-fit">
            Marquer comme envoyée
          </Button>
        </div>
      )}
    </Card>
  );
}
```

- [ ] **Step 3: Run the test again to confirm no regressions**

Run: `cd frontend && npx vitest run components/ApplicationCard.test.tsx`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/components/ApplicationCard.tsx
git commit -m "style: restyle ApplicationCard with Card, Button, and Badge"
```

---

### Task 15: `SearchCriteriaForm`

**Files:**
- Modify: `frontend/components/SearchCriteriaForm.tsx`

**Interfaces:**
- Consumes: `Card` (Task 3), `Button` (Task 2), `Input` (Task 5).
- Produces: no change to public props/exports (`SearchCriteriaFormValue`, `EMPTY_SEARCH_CRITERIA_FORM_VALUE`, `toSearchCriteria`).

- [ ] **Step 1: Run the existing test to confirm the baseline is green**

Run: `cd frontend && npx vitest run components/SearchCriteriaForm.test.tsx`
Expected: PASS

- [ ] **Step 2: Restyle**

```tsx
// frontend/components/SearchCriteriaForm.tsx
"use client";

import { Card } from "./ui/Card";
import { Button } from "./ui/Button";
import { Input } from "./ui/Field";
import type { SearchCriteria } from "@/lib/types";

export interface SearchCriteriaFormValue {
  keywords: string;
  location: string;
  contractType: string;
  remote: boolean;
  excludeKeywords: string;
}

export const EMPTY_SEARCH_CRITERIA_FORM_VALUE: SearchCriteriaFormValue = {
  keywords: "",
  location: "",
  contractType: "",
  remote: false,
  excludeKeywords: "",
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
    <Card className="flex flex-col gap-4 p-4">
      <label className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-300">
        Mots-clés
        <Input
          type="text"
          value={value.keywords}
          onChange={(event) => onChange({ ...value, keywords: event.target.value })}
          placeholder="ex: développeur python"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-300">
        Localisation
        <Input
          type="text"
          value={value.location}
          onChange={(event) => onChange({ ...value, location: event.target.value })}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-300">
        Type de contrat
        <Input
          type="text"
          value={value.contractType}
          onChange={(event) => onChange({ ...value, contractType: event.target.value })}
          placeholder="ex: CDI"
        />
      </label>
      <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
        <input
          type="checkbox"
          checked={value.remote}
          onChange={(event) => onChange({ ...value, remote: event.target.checked })}
          className="h-4 w-4 rounded border-slate-300 text-amber-600 focus:ring-amber-500 dark:border-ink-800"
        />
        Télétravail uniquement
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-300">
        Mots-clés à exclure (séparés par des virgules)
        <Input
          type="text"
          value={value.excludeKeywords}
          onChange={(event) => onChange({ ...value, excludeKeywords: event.target.value })}
        />
      </label>
      <Button onClick={onSearch} disabled={value.keywords.trim().length === 0} isLoading={isSearching} className="w-fit">
        {isSearching ? "Recherche en cours..." : "Rechercher"}
      </Button>
    </Card>
  );
}
```

- [ ] **Step 3: Run the test again to confirm no regressions**

Run: `cd frontend && npx vitest run components/SearchCriteriaForm.test.tsx`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/components/SearchCriteriaForm.tsx
git commit -m "style: restyle SearchCriteriaForm with Card, Button, and Input"
```

---

### Task 16: `JobListingsList`

**Files:**
- Modify: `frontend/components/JobListingsList.tsx`

**Interfaces:**
- Consumes: `Card` (Task 3), `Button` (Task 2), `lucide-react`'s `SearchX` icon.
- Produces: no change to public props.

- [ ] **Step 1: Run the existing test to confirm the baseline is green**

Run: `cd frontend && npx vitest run components/JobListingsList.test.tsx`
Expected: PASS

- [ ] **Step 2: Restyle**

```tsx
// frontend/components/JobListingsList.tsx
"use client";

import { useState } from "react";
import { SearchX } from "lucide-react";
import { Card } from "./ui/Card";
import { Button } from "./ui/Button";
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
        <p className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
          Sources indisponibles pour cette recherche : {unavailableSources.join(", ")}
        </p>
      )}

      {listings.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-10 text-center">
          <SearchX className="h-6 w-6 text-slate-400 dark:text-slate-500" aria-hidden="true" />
          <p className="text-sm text-slate-600 dark:text-slate-400">Aucune offre trouvée pour ces critères.</p>
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {listings.map((listing) => (
            <li key={listing.url}>
              <Card className="flex items-start gap-3 p-4">
                <input
                  type="checkbox"
                  aria-label={listing.title}
                  checked={selectedUrls.has(listing.url)}
                  onChange={() => toggle(listing.url)}
                  className="mt-1 h-4 w-4 rounded border-slate-300 text-amber-600 focus:ring-amber-500 dark:border-ink-800"
                />
                <div>
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">{listing.title}</p>
                  <p className="text-sm text-slate-600 dark:text-slate-400">
                    {listing.company}
                    {listing.location ? ` — ${listing.location}` : ""}
                  </p>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-500">{listing.snippet}</p>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      <Button onClick={handleCreate} disabled={selectedUrls.size === 0} isLoading={isCreating} className="mt-4">
        {isCreating ? "Lancement en cours..." : `Lancer le diagnostic pour la sélection (${selectedUrls.size})`}
      </Button>
    </div>
  );
}
```

- [ ] **Step 3: Run the test again to confirm no regressions**

Run: `cd frontend && npx vitest run components/JobListingsList.test.tsx`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/components/JobListingsList.tsx
git commit -m "style: restyle JobListingsList with Card, Button, and an empty state"
```

---

### Task 17: `CandidateProfileForm`

**Files:**
- Modify: `frontend/components/CandidateProfileForm.tsx`

**Interfaces:**
- Consumes: `Card` (Task 3), `Button` (Task 2), `Input` (Task 5).
- Produces: no change to public props/exports.

- [ ] **Step 1: Run the existing test to confirm the baseline is green**

Run: `cd frontend && npx vitest run components/CandidateProfileForm.test.tsx`
Expected: PASS

- [ ] **Step 2: Restyle**

```tsx
// frontend/components/CandidateProfileForm.tsx
"use client";

import { Card } from "./ui/Card";
import { Button } from "./ui/Button";
import { Input } from "./ui/Field";
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
    <Card className="flex flex-col gap-4 p-4">
      {FIELDS.map(({ key, label, required }) => (
        <label key={key} className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-300">
          {label}
          <Input
            type="text"
            value={value[key]}
            required={required}
            onChange={(event) => onChange({ ...value, [key]: event.target.value })}
          />
        </label>
      ))}
      <Button onClick={onSubmit} isLoading={isSubmitting} className="w-fit">
        {isSubmitting ? "Enregistrement..." : "Enregistrer"}
      </Button>
    </Card>
  );
}
```

- [ ] **Step 3: Run the test again to confirm no regressions**

Run: `cd frontend && npx vitest run components/CandidateProfileForm.test.tsx`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/components/CandidateProfileForm.tsx
git commit -m "style: restyle CandidateProfileForm with Card, Button, and Input"
```

---

### Task 18: `AuthForm`

**Files:**
- Modify: `frontend/components/AuthForm.tsx`

**Interfaces:**
- Consumes: `Button` (Task 2), `Input` (Task 5).
- Produces: no change to public props.

- [ ] **Step 1: Run the existing test to confirm the baseline is green**

Run: `cd frontend && npx vitest run components/AuthForm.test.tsx`
Expected: PASS

- [ ] **Step 2: Restyle**

```tsx
// frontend/components/AuthForm.tsx
"use client";

import { useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api";
import { Button } from "./ui/Button";
import { Input } from "./ui/Field";

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
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-amber-600 dark:text-amber-400">Diagnostic ATS</p>
        <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-50">
          {mode === "login" ? "Connexion" : "Inscription"}
        </h1>
      </div>
      {formError && (
        <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {formError}
        </p>
      )}
      <label className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-300">
        Email
        <Input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        {emailError && <span className="text-sm text-red-600 dark:text-red-400">{emailError}</span>}
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-300">
        Mot de passe
        <Input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
      </label>
      <Button type="submit" isLoading={isSubmitting}>
        {mode === "login" ? "Se connecter" : "Créer mon compte"}
      </Button>
      <button
        type="button"
        onClick={() => onModeChange(mode === "login" ? "register" : "login")}
        className="text-sm font-semibold text-amber-700 underline dark:text-amber-400"
      >
        {mode === "login" ? "Pas de compte ? S'inscrire" : "Déjà un compte ? Se connecter"}
      </button>
    </form>
  );
}
```

- [ ] **Step 3: Run the test again to confirm no regressions**

Run: `cd frontend && npx vitest run components/AuthForm.test.tsx`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/components/AuthForm.tsx
git commit -m "style: restyle AuthForm with Button and Input"
```

---

### Task 19: Login page

**Files:**
- Modify: `frontend/app/login/page.tsx`

**Interfaces:**
- Consumes: `AuthForm` (Task 18, unchanged props).
- Produces: no change (no test file exists for this page).

- [ ] **Step 1: Restyle**

```tsx
// frontend/app/login/page.tsx
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
    <main className="mx-auto flex min-h-screen max-w-sm items-center px-6">
      <AuthForm mode={mode} onModeChange={setMode} onSubmit={handleSubmit} />
    </main>
  );
}
```

- [ ] **Step 2: Run the full suite to confirm no regressions**

Run: `cd frontend && npm test`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/app/login/page.tsx
git commit -m "style: restyle login page layout"
```

---

### Task 20: Diagnostic page

**Files:**
- Modify: `frontend/app/diagnostic/page.tsx`

**Interfaces:**
- Consumes: `Button` (Task 2), `CVDropzone`/`OfferInput`/`DiagnosticReportView`/`ErrorBanner`/`PersonalizedDocumentCard` (unchanged props from earlier tasks).
- Produces: no change (`app/page.test.tsx` tests the root redirect page, not this one — unaffected).

- [ ] **Step 1: Restyle**

```tsx
// frontend/app/diagnostic/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/RequireAuth";
import { CVDropzone } from "@/components/CVDropzone";
import { OfferInput, EMPTY_OFFER_VALUE, type OfferInputValue } from "@/components/OfferInput";
import { DiagnosticReportView } from "@/components/DiagnosticReportView";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PersonalizedDocumentCard } from "@/components/PersonalizedDocumentCard";
import { Button } from "@/components/ui/Button";
import { toBannerContent, isSessionExpired, type BannerContent } from "@/lib/errors";
import { createDiagnostic, downloadCv, downloadLetter, generateCv, generateLetter } from "@/lib/api";
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
    <main className="mx-auto max-w-2xl px-8 py-10">
      <p className="text-xs font-bold uppercase tracking-wide text-amber-600 dark:text-amber-400">Diagnostic</p>
      <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-50">Analyser un CV</h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
        Uploadez votre CV et l&apos;offre visée pour comprendre ce qui bloque côté ATS.
      </p>

      <div className="mt-6 flex flex-col gap-4">
        <CVDropzone file={file} onFileSelected={setFile} />
        <OfferInput value={offer} onChange={setOffer} />
        {banner && <ErrorBanner content={banner} />}
        <Button onClick={handleSubmit} disabled={!canSubmit} isLoading={isSubmitting} className="w-fit">
          {isSubmitting ? "Analyse en cours, ça prend quelques secondes..." : "Analyser mon CV"}
        </Button>
      </div>

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
    </main>
  );
}
```

- [ ] **Step 2: Run the full suite to confirm no regressions**

Run: `cd frontend && npm test`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/app/diagnostic/page.tsx
git commit -m "style: restyle diagnostic page layout"
```

---

### Task 21: Candidatures page

**Files:**
- Modify: `frontend/app/candidatures/page.tsx`

**Interfaces:**
- Consumes: `SearchCriteriaForm`/`JobListingsList`/`ApplicationCard`/`ErrorBanner` (unchanged props from earlier tasks).
- Produces: no change (no test file exists for this page).

- [ ] **Step 1: Restyle**

```tsx
// frontend/app/candidatures/page.tsx
"use client";

import { useRef, useState } from "react";
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
import { pollJobSearchDiscovery } from "@/lib/discoveryPolling";
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
  const [isDiscovering, setIsDiscovering] = useState(false);
  const cancelPollRef = useRef<(() => void) | null>(null);

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
    cancelPollRef.current?.();
    setIsDiscovering(false);
    try {
      const result = await searchJobs(token, toSearchCriteria(criteria));
      setSearchResult(result);
      if (result.discovery_pending) {
        setIsDiscovering(true);
        cancelPollRef.current = pollJobSearchDiscovery(
          token,
          result.search_id,
          (newListings) => {
            setSearchResult((prev) => (prev ? { ...prev, listings: [...prev.listings, ...newListings] } : prev));
          },
          () => setIsDiscovering(false)
        );
      }
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
    <main className="mx-auto max-w-2xl px-8 py-10">
      <p className="text-xs font-bold uppercase tracking-wide text-amber-600 dark:text-amber-400">Candidatures</p>
      <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-50">
        Trouver et postuler à des offres
      </h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
        Définissez vos critères, sélectionnez les offres qui vous intéressent, puis relisez chaque candidature avant
        l&apos;envoi.
      </p>

      <div className="mt-6">
        <SearchCriteriaForm value={criteria} onChange={setCriteria} onSearch={handleSearch} isSearching={isSearching} />
      </div>

      {isDiscovering && (
        <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
          Recherche en cours sur les sites des entreprises...
        </p>
      )}

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
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-50">Vos candidatures</h2>
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

- [ ] **Step 2: Run the full suite to confirm no regressions**

Run: `cd frontend && npm test`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/app/candidatures/page.tsx
git commit -m "style: restyle candidatures page layout"
```

---

### Task 22: Historique page

**Files:**
- Modify: `frontend/app/historique/page.tsx`

**Interfaces:**
- Consumes: `Card` (Task 3), `ApplicationCard`/`DiagnosticReportView`/`ErrorBanner`/`ConfirmDialog` (unchanged), `lucide-react`'s `ChevronDown`/`Inbox` icons.
- Produces: no change (no test file exists for this page).

- [ ] **Step 1: Restyle**

```tsx
// frontend/app/historique/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, Inbox } from "lucide-react";
import { RequireAuth } from "@/components/RequireAuth";
import { DiagnosticReportView } from "@/components/DiagnosticReportView";
import { ApplicationCard } from "@/components/ApplicationCard";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Card } from "@/components/ui/Card";
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
    <main className="mx-auto max-w-2xl px-8 py-10">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-amber-600 dark:text-amber-400">Historique</p>
          <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-50">Historique</h1>
        </div>
        {(diagnostics.length > 0 || applications.length > 0) && (
          <button
            type="button"
            onClick={() => setIsConfirmOpen(true)}
            className="text-sm font-semibold text-red-600 dark:text-red-400"
          >
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
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-50">Candidatures</h2>
          <ul className="mt-3 flex flex-col gap-3">
            {applications.map((application) => {
              const isExpanded = expandedApplicationId === application.id;
              return (
                <li key={application.id}>
                  <Card className="p-4">
                    <button
                      type="button"
                      onClick={() => setExpandedApplicationId(isExpanded ? null : application.id)}
                      className="flex w-full items-center justify-between text-left"
                    >
                      <span className="text-sm font-semibold text-slate-900 dark:text-slate-50">
                        {application.job_title} — {application.company_name}
                      </span>
                      <span className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                        {new Date(application.created_at).toLocaleDateString("fr-FR")}
                        <ChevronDown
                          className={`h-4 w-4 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                          aria-hidden="true"
                        />
                      </span>
                    </button>
                    {isExpanded && token && (
                      <div className="mt-4">
                        <ApplicationCard application={application} token={token} onUpdated={handleApplicationUpdated} />
                      </div>
                    )}
                  </Card>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <div className="mt-8">
        {applications.length > 0 && <h2 className="text-lg font-bold text-slate-900 dark:text-slate-50">Diagnostics</h2>}
        {!isLoading && diagnostics.length === 0 && applications.length === 0 && (
          <div className="mt-6 flex flex-col items-center gap-2 py-10 text-center">
            <Inbox className="h-6 w-6 text-slate-400 dark:text-slate-500" aria-hidden="true" />
            <p className="text-sm text-slate-600 dark:text-slate-400">Aucun diagnostic pour le moment.</p>
          </div>
        )}

        <ul className="mt-3 flex flex-col gap-3">
          {diagnostics.map((diagnostic) => {
            const isExpanded = expandedId === diagnostic.id;
            return (
              <li key={diagnostic.id}>
                <Card className="p-4">
                  <button
                    type="button"
                    onClick={() => setExpandedId(isExpanded ? null : diagnostic.id)}
                    className="flex w-full items-center justify-between text-left"
                  >
                    <span className="text-sm font-semibold text-slate-900 dark:text-slate-50">
                      {new Date(diagnostic.created_at).toLocaleDateString("fr-FR")}
                    </span>
                    <span className="flex items-center gap-2 text-sm font-bold text-amber-600 dark:text-amber-400">
                      {diagnostic.overall_score}/100
                      <ChevronDown
                        className={`h-4 w-4 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                        aria-hidden="true"
                      />
                    </span>
                  </button>
                  {isExpanded && (
                    <div className="mt-4">
                      <DiagnosticReportView report={diagnostic} />
                    </div>
                  )}
                </Card>
              </li>
            );
          })}
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

- [ ] **Step 2: Run the full suite to confirm no regressions**

Run: `cd frontend && npm test`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/app/historique/page.tsx
git commit -m "style: restyle historique page with Card, chevrons, and an empty state"
```

---

### Task 23: Profil page

**Files:**
- Modify: `frontend/app/profil/page.tsx`

**Interfaces:**
- Consumes: `Card` (Task 3), `Button` (Task 2), `CandidateProfileForm`/`CVDropzone`/`ErrorBanner` (unchanged).
- Produces: no change (no test file exists for this page).

- [ ] **Step 1: Restyle**

```tsx
// frontend/app/profil/page.tsx
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
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
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
    <main className="mx-auto max-w-2xl px-8 py-10">
      <p className="text-xs font-bold uppercase tracking-wide text-amber-600 dark:text-amber-400">Profil</p>
      <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-50">
        Mon profil candidat
      </h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
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

      <Card className="mt-6 p-4">
        <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">CV de référence</p>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          {profile?.has_cv ? `Fichier actuel : ${profile.cv_filename}` : "Aucun CV de référence uploadé pour le moment."}
        </p>
        <div className="mt-3 flex flex-col gap-3">
          <CVDropzone file={cvFile} onFileSelected={setCvFile} />
          <Button onClick={handleUploadCv} disabled={!cvFile} isLoading={isUploadingCv} className="w-fit">
            {isUploadingCv ? "Envoi en cours..." : "Uploader mon CV de référence"}
          </Button>
        </div>
      </Card>
    </main>
  );
}
```

- [ ] **Step 2: Run the full suite to confirm no regressions**

Run: `cd frontend && npm test`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/app/profil/page.tsx
git commit -m "style: restyle profil page layout"
```

---

## Final check

After Task 23, run the full suite once more and eyeball the app in a browser (`npm run dev` from `frontend/`) across all 5 pages in both light and dark OS theme, logged in and logged out, to catch anything the automated tests can't (spacing, contrast, dark-mode contrast on the sidebar and cards):

```bash
cd frontend && npm test && npm run dev
```
