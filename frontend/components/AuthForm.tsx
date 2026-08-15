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
    <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-accent-strong">Diagnostic ATS</p>
        <h1 className="mt-1.5 font-display text-2xl font-bold text-ink">
          {mode === "login" ? "Connexion" : "Inscription"}
        </h1>
        <p className="mt-1.5 text-sm text-ink-soft">
          {mode === "login" ? "Content de te revoir." : "Quelques secondes suffisent pour commencer."}
        </p>
      </div>
      {formError && (
        <p role="alert" className="rounded-2xl bg-attention-soft px-4 py-2.5 text-sm font-medium text-attention-ink">
          {formError}
        </p>
      )}
      <label className="flex flex-col gap-1.5 text-[13px] font-semibold text-ink-soft">
        Email
        <Input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        {emailError && <span className="text-sm font-medium text-attention-ink">{emailError}</span>}
      </label>
      <label className="flex flex-col gap-1.5 text-[13px] font-semibold text-ink-soft">
        Mot de passe
        <Input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
      </label>
      <Button type="submit" isLoading={isSubmitting} className="mt-1">
        {mode === "login" ? "Se connecter" : "Créer mon compte"}
      </Button>
      <button
        type="button"
        onClick={() => onModeChange(mode === "login" ? "register" : "login")}
        className="text-center text-sm font-semibold text-accent-strong"
      >
        {mode === "login" ? "Pas de compte ? S'inscrire" : "Déjà un compte ? Se connecter"}
      </button>
    </form>
  );
}
