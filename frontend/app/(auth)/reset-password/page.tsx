"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { resetPassword } from "@/lib/api";

function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Le mot de passe doit contenir au moins 8 caractères.");
      return;
    }
    if (password !== confirm) {
      setError("Les mots de passe ne correspondent pas.");
      return;
    }
    setIsLoading(true);
    try {
      await resetPassword(token, password);
      router.push("/login");
    } catch {
      setError(
        "Lien invalide ou expiré. Redemande une réinitialisation depuis la page « Mot de passe oublié »."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md space-y-8">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-primary-600/10 rounded-xl">
          <Sparkles className="w-6 h-6 text-primary-600" />
        </div>
        <span className="text-2xl font-display font-bold tracking-tight text-foreground">
          Search
        </span>
      </div>

      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">
          Nouveau mot de passe
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Choisis un nouveau mot de passe pour ton compte.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 bg-destructive/10 border border-destructive/20 text-destructive text-xs rounded-xl">
            {error}
          </div>
        )}
        <Input
          label="Nouveau mot de passe"
          type="password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <Input
          label="Confirmer le mot de passe"
          type="password"
          placeholder="••••••••"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
        />
        <Button
          type="submit"
          variant="primary"
          size="lg"
          fullWidth
          isLoading={isLoading}
        >
          Réinitialiser
        </Button>
      </form>

      <a
        href="/mot-de-passe-oublie"
        className="text-xs font-medium text-primary-600 hover:underline"
      >
        Demander un nouveau lien
      </a>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-card p-6">
      <Suspense fallback={null}>
        <ResetPasswordForm />
      </Suspense>
    </div>
  );
}
