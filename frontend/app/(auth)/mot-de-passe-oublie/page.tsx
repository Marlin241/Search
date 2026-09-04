"use client";

import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Logo } from "@/components/common/Logo";
import { forgotPassword } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await forgotPassword(email);
    } catch {
      /* on n'expose jamais d'erreur ici (pas d'énumération de comptes) */
    } finally {
      setIsLoading(false);
      setSent(true);
    }
  };

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-card p-6">
      <div className="w-full max-w-md space-y-8">
        <Logo />

        <div>
          <h1 className="text-2xl font-display font-bold text-foreground">
            Mot de passe oublié
          </h1>
          <p className="text-sm text-muted-foreground mt-1.5">
            Entre ton adresse email : si un compte existe, tu recevras un lien
            pour choisir un nouveau mot de passe.
          </p>
        </div>

        {sent ? (
          <div className="p-4 bg-muted rounded-xl text-sm text-foreground">
            Si un compte existe pour cette adresse, un email de
            réinitialisation vient d&apos;être envoyé. Pense à vérifier tes
            spams.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Adresse email"
              type="email"
              placeholder="votre.nom@exemple.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Button
              type="submit"
              variant="primary"
              size="lg"
              fullWidth
              isLoading={isLoading}
            >
              Envoyer le lien
            </Button>
          </form>
        )}

        <a
          href="/login"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-primary-600 hover:underline"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Retour à la connexion
        </a>
      </div>
    </div>
  );
}
