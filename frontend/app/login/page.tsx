"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check } from "lucide-react";
import { AuthForm } from "@/components/AuthForm";
import { useAuth } from "@/context/AuthContext";

const BENEFITS = [
  { text: "Un score clair en moins d'une minute", chip: "bg-accent" },
  { text: "CV et lettre réécrits par l'IA, prêts à relire", chip: "bg-accent2" },
  { text: "Toutes tes candidatures suivies au même endroit", chip: "bg-pending" },
] as const;

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
    <main className="flex min-h-screen flex-col md:flex-row">
      <div className="relative hidden flex-1 flex-col justify-center gap-5 overflow-hidden bg-gradient-to-br from-ink via-[oklch(0.30_0.05_32)] to-[oklch(0.34_0.09_25)] px-12 py-14 text-[oklch(0.97_0.01_60)] md:flex">
        <div className="blob h-[280px] w-[280px] bg-accent/35" style={{ top: "-90px", right: "-80px" }} />
        <div
          className="blob h-[220px] w-[220px] bg-accent2/20"
          style={{ bottom: "-70px", left: "-60px", animationDelay: "-4s" }}
        />

        <span className="relative w-fit rounded-full bg-[oklch(0.4_0.09_38)] px-4 py-1.5 text-xs font-bold tracking-wide text-[oklch(0.93_0.08_45)]">
          ✨ Candidatures accompagnées par l&apos;IA
        </span>
        <h1 className="relative max-w-md font-display text-[46px] font-extrabold leading-[1.08] tracking-tight">
          Comprends ton CV comme un recruteur le voit.
        </h1>
        <p className="relative max-w-sm text-base text-[oklch(0.85_0.02_55)]">
          Diagnostic ATS analyse ton CV face à chaque offre, explique ce qui coince et t&apos;aide à corriger le tir,
          étape par étape.
        </p>
        <ul className="relative mt-2 flex flex-col gap-3.5">
          {BENEFITS.map(({ text, chip }) => (
            <li key={text} className="flex items-center gap-3 text-sm font-semibold text-[oklch(0.94_0.015_55)]">
              <span className={`flex h-[30px] w-[30px] flex-shrink-0 items-center justify-center rounded-[11px] text-ink-on-accent ${chip}`}>
                <Check className="h-3.5 w-3.5" strokeWidth={3} aria-hidden="true" />
              </span>
              {text}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-1 items-center justify-center bg-bg px-6 py-14">
        <div className="w-full max-w-sm rounded-[32px] border border-border bg-surface p-8 shadow-pop">
          <AuthForm mode={mode} onModeChange={setMode} onSubmit={handleSubmit} />
        </div>
      </div>
    </main>
  );
}
