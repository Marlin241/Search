/**
 * Identité de marque du produit, centralisée.
 * Le nom définitif n'est pas encore choisi : "Search" est provisoire.
 * Tout affichage du nom passe par ces constantes — jamais de "Search" en dur.
 */
export const PRODUCT_NAME = "Search";
export const TAGLINE =
  "Le copilote IA pour décrocher ton job, où que tu sois.";
export const PARENT_NAME = "Yokkute Labs";
export const PARENT_URL = "https://yokkutelabs.com";
export const CONTACT_EMAIL = "yokkutelabs@gmail.com";
/** URL publique du produit — sert de base pour les métadonnées OpenGraph. */
export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://search.yokkutelabs.com";
