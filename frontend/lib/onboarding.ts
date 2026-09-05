import type { CandidateProfileOut } from "@/lib/types";

/**
 * Un profil est considéré "onboardé" dès qu'il porte les deux champs que le
 * wizard rend obligatoires avant de pouvoir le terminer (métiers recherchés
 * à l'étape 1, CV à l'étape 3) - pas besoin d'un flag dédié en base.
 */
export function isOnboardingComplete(profile: CandidateProfileOut | null): boolean {
  return !!profile && profile.has_cv && !!profile.desired_job_titles?.length;
}
