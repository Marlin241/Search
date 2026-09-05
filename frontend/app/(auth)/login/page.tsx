"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle, AlertCircle, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { LegalFooter } from "@/components/common/LegalFooter";
import { Logo } from "@/components/common/Logo";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";

export default function LoginPage() {
  const router = useRouter();
  const { login, register, isLoading: authLoading } = useAuth();

  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email || !password) {
      setError("Veuillez remplir tous les champs.");
      return;
    }

    if (!isLogin && password !== confirmPassword) {
      setError("Les mots de passe ne correspondent pas.");
      return;
    }

    if (!isLogin && password.length < 8) {
      setError("Le mot de passe doit contenir au moins 8 caractères.");
      return;
    }

    if (!isLogin && !inviteCode.trim()) {
      setError("Un code d'invitation est requis pour créer un compte.");
      return;
    }

    if (!isLogin && !acceptTerms) {
      setError(
        "Vous devez accepter les conditions d'utilisation et la politique de confidentialité."
      );
      return;
    }

    setIsLoading(true);
    try {
      if (isLogin) {
        await login(email, password);
        router.push("/dashboard");
      } else {
        await register(email, password, inviteCode.trim());
        router.push("/onboarding");
      }
    } catch (err: any) {
      setError(err?.detail || err?.message || "Une erreur est survenue.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen w-full bg-background">
      {/* LEFT panel - Hero (Talya style) */}
      <div className="hidden lg:flex w-1/2 flex-col justify-between bg-gradient-to-br from-primary-600 via-primary-500 to-accent p-12 text-white relative overflow-hidden">
        {/* Glow background effects */}
        <div className="absolute top-0 left-0 w-full h-full overflow-hidden opacity-20 pointer-events-none">
          <div className="absolute -top-[15%] -left-[15%] w-[60%] h-[60%] rounded-full bg-white blur-3xl mix-blend-overlay" />
          <div className="absolute bottom-[10%] -right-[15%] w-[60%] h-[60%] rounded-full bg-accent blur-3xl mix-blend-overlay" />
        </div>

        <div className="relative z-10">
          <Logo className="mb-16 text-white" />

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="max-w-md"
          >
            <h1 className="text-4xl lg:text-5xl font-display font-bold leading-tight mb-6">
              Le copilote IA pour décrocher ton job idéal.
            </h1>
            <p className="text-white/80 text-base leading-relaxed mb-8">
              Trouve les offres compatibles, réécris ton CV pour maximiser ton score ATS, et pilote tes candidatures.
            </p>

            <div className="space-y-4">
              {[
                "Offres agrégées en temps réel",
                "Diagnostic ATS instantané & mots-clés manquants",
                "CV & lettres de motivation ultra-personnalisés par IA",
              ].map((feature, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.2 + i * 0.1, duration: 0.4 }}
                  className="flex items-center gap-3"
                >
                  <div className="bg-white/20 p-1 rounded-full shrink-0">
                    <CheckCircle className="w-4 h-4 text-white" />
                  </div>
                  <span className="text-sm font-medium text-white/90">{feature}</span>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Floating preview badge */}
        <div className="relative z-10 flex justify-end">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.6 }}
            className="bg-white/10 backdrop-blur-md border border-white/20 p-4 rounded-2xl w-80 shadow-2xl space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-white/90">Score de compatibilité</span>
              <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-success text-white">92%</span>
            </div>
            <p className="text-xs text-white/70">Lead Developer Full Stack · Alan (Paris)</p>
            <div className="h-1.5 w-full bg-white/20 rounded-full overflow-hidden">
              <div className="h-full bg-white rounded-full w-[92%]" />
            </div>
          </motion.div>
        </div>
      </div>

      {/* RIGHT panel - Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-6 sm:p-12 bg-card">
        <div className="w-full max-w-md space-y-8">
          <div>
            <h2 className="text-2xl font-display font-bold text-foreground">
              {isLogin ? "Ravi de vous revoir" : "Commencer gratuitement"}
            </h2>
            <p className="text-sm text-muted-foreground mt-1.5">
              {isLogin
                ? "Connectez-vous pour continuer votre recherche d'emploi."
                : "Créez votre compte en 30 secondes sans engagement."}
            </p>
          </div>

          {/* Switch tabs */}
          <div className="bg-muted p-1 rounded-xl flex">
            <button
              onClick={() => { setIsLogin(true); setError(null); }}
              className={cn(
                "flex-1 py-2 px-4 text-xs font-semibold rounded-lg transition-all",
                isLogin ? "bg-card text-foreground shadow-soft" : "text-muted-foreground hover:text-foreground"
              )}
            >
              Connexion
            </button>
            <button
              onClick={() => { setIsLogin(false); setError(null); }}
              className={cn(
                "flex-1 py-2 px-4 text-xs font-semibold rounded-lg transition-all",
                !isLogin ? "bg-card text-foreground shadow-soft" : "text-muted-foreground hover:text-foreground"
              )}
            >
              Inscription
            </button>
          </div>

          {/* Form */}
          {/* noValidate : on gère toute la validation nous-mêmes (voir
             handleSubmit) pour un message et un style d'erreur cohérents -
             sans ça, la bulle de validation native du navigateur intercepte
             les champs vides avant que notre message custom ne s'affiche. */}
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {error && (
              <div className="p-3 bg-destructive/10 border border-destructive/20 text-destructive text-xs rounded-xl flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                <p className="font-medium">{error}</p>
              </div>
            )}

            <Input
              label="Adresse email"
              type="email"
              placeholder="votre.nom@exemple.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />

            <Input
              label="Mot de passe"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />

            {isLogin && (
              <div className="text-right -mt-2">
                <a
                  href="/mot-de-passe-oublie"
                  className="text-xs font-medium text-primary-600 hover:underline"
                >
                  Mot de passe oublié ?
                </a>
              </div>
            )}

            {!isLogin && (
              <>
                <Input
                  label="Confirmer le mot de passe"
                  type="password"
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />

                <Input
                  label="Code d'invitation"
                  type="text"
                  placeholder="Ton code d'accès à la beta"
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value)}
                  required
                />

                <label className="flex items-start gap-2.5 text-xs text-muted-foreground">
                  <input
                    type="checkbox"
                    className="mt-0.5 shrink-0"
                    checked={acceptTerms}
                    onChange={(e) => setAcceptTerms(e.target.checked)}
                  />
                  <span>
                    J&apos;accepte les{" "}
                    <a
                      href="/conditions"
                      target="_blank"
                      className="text-primary-600 hover:underline"
                    >
                      conditions d&apos;utilisation
                    </a>{" "}
                    et la{" "}
                    <a
                      href="/confidentialite"
                      target="_blank"
                      className="text-primary-600 hover:underline"
                    >
                      politique de confidentialité
                    </a>
                    .
                  </span>
                </label>
              </>
            )}

            <Button
              type="submit"
              variant="primary"
              size="lg"
              fullWidth
              isLoading={isLoading || authLoading}
              icon={<ArrowRight className="w-4 h-4" />}
            >
              {isLogin ? "Se connecter" : "Créer mon compte"}
            </Button>
          </form>

          <LegalFooter />
        </div>
      </div>
    </div>
  );
}
