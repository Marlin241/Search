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
