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
