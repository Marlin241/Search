"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check } from "lucide-react";
import { AuthForm } from "@/components/AuthForm";
import { useAuth } from "@/context/AuthContext";

const BENEFITS = ["Diagnostic en 30 secondes", "CV et lettre réécrits par l'IA", "Candidatures suivies au même endroit"];

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
    <main className="flex min-h-screen">
      <div className="auth-bg-grid relative hidden w-[46%] flex-col justify-center bg-ink-950 px-12 py-10 text-slate-50 md:flex">
        <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-amber-900 bg-amber-950 px-3 py-1 text-xs font-bold uppercase tracking-wide text-amber-400">
          ✨ Candidatures boostées par l&apos;IA
        </span>
        <h1 className="mt-4 max-w-sm text-3xl font-extrabold leading-tight tracking-tight">
          Comprends pourquoi ton CV est recalé par les ATS.
        </h1>
        <ul className="mt-6 flex flex-col gap-2 text-sm text-slate-300">
          {BENEFITS.map((benefit) => (
            <li key={benefit} className="flex items-center gap-2">
              <Check className="h-4 w-4 flex-shrink-0 text-amber-400" aria-hidden="true" />
              {benefit}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-1 items-center justify-center bg-slate-50 px-6 dark:bg-ink-950">
        <div className="w-full max-w-sm">
          <AuthForm mode={mode} onModeChange={setMode} onSubmit={handleSubmit} />
        </div>
      </div>
    </main>
  );
}
