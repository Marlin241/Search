"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { isOnboardingComplete } from "@/lib/onboarding";

type OnboardingGate = "block-if-incomplete" | "block-if-complete";

export function RequireAuth({
  children,
  onboardingGate,
}: {
  children: React.ReactNode;
  /**
   * "block-if-incomplete" (pages de l'app) : renvoie vers /onboarding tout
   * compte qui n'a pas encore de métiers recherchés + CV enregistrés.
   * "block-if-complete" (page /onboarding elle-même) : renvoie vers
   * /dashboard un compte déjà onboardé, pour ne jamais lui réafficher un
   * wizard vide qui écraserait son profil réel s'il allait au bout.
   * Omis : aucune contrainte liée à l'onboarding. Les comptes admin ne sont
   * jamais soumis à cette contrainte (leur usage de l'app est indépendant
   * du profil candidat).
   */
  onboardingGate?: OnboardingGate;
}) {
  const { user, isLoading, profile, isProfileLoading } = useAuth();
  const router = useRouter();

  const gateActive = !!onboardingGate && !!user && !user.is_admin;
  const gateReady = !gateActive || !isProfileLoading;
  const complete = isOnboardingComplete(profile);
  const blocked =
    gateActive &&
    gateReady &&
    ((onboardingGate === "block-if-incomplete" && !complete) ||
      (onboardingGate === "block-if-complete" && complete));

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
      return;
    }
    if (!blocked) return;
    router.replace(onboardingGate === "block-if-complete" ? "/dashboard" : "/onboarding");
  }, [user, isLoading, blocked, onboardingGate, router]);

  if (isLoading || (gateActive && !gateReady)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm font-medium text-muted-foreground">Chargement...</p>
        </div>
      </div>
    );
  }

  if (!user || blocked) return null;

  return <>{children}</>;
}
