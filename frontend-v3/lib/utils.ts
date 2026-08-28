import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes safely (deduplication + conditional) */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * True only for http(s) URLs. Used before rendering an LLM-sourced URL
 * (e.g. a web-search citation) as a clickable link: the model's output can
 * be influenced by content it read during search, so an href built from it
 * must not be trusted to be a safe scheme (javascript:, data:, etc.).
 */
export function isSafeHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

/** Format a date string into a human-readable French format */
export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Format a date string into a relative time (e.g. "il y a 3 jours") */
export function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  const diffH = Math.floor(diffMs / 3600000);
  const diffD = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return "À l'instant";
  if (diffMin < 60) return `Il y a ${diffMin} min`;
  if (diffH < 24) return `Il y a ${diffH}h`;
  if (diffD < 7) return `Il y a ${diffD}j`;
  return formatDate(dateStr);
}

/** Get initials from a company name (max 2 chars) */
export function getInitials(name: string): string {
  return name
    .split(/[\s-]+/)
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

/** Humanize application status labels */
export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    en_cours: "En cours",
    soumise_auto: "Envoyée (auto)",
    a_soumettre_manuellement: "À envoyer",
    soumise_manuelle_confirmee: "Envoyée",
    echec_soumission: "Échec",
  };
  return map[status] ?? status;
}

/** Map status to a semantic color variant */
export function statusVariant(
  status: string
): "success" | "warning" | "destructive" | "default" | "accent" {
  const map: Record<string, "success" | "warning" | "destructive" | "default" | "accent"> = {
    en_cours: "default",
    soumise_auto: "success",
    a_soumettre_manuellement: "warning",
    soumise_manuelle_confirmee: "success",
    echec_soumission: "destructive",
  };
  return map[status] ?? "default";
}

/** Humanize source labels */
export function sourceLabel(source: string): string {
  const map: Record<string, string> = {
    france_travail: "France Travail",
    adzuna: "Adzuna",
    la_bonne_alternance: "La Bonne Alternance",
    greenhouse: "Greenhouse",
    lever: "Lever",
    reliefweb: "ReliefWeb",
    jobicy: "Jobicy",
    weworkremotely: "We Work Remotely",
    ngojobs: "NGO Jobs in Africa",
    emploi_dakar: "Emploi Dakar",
    crawled: "Job board local",
  };
  return map[source] ?? source;
}

/** Determine score color based on value */
export function scoreColor(score: number): string {
  if (score >= 70) return "text-success";
  if (score >= 40) return "text-warning";
  return "text-destructive";
}

/** Determine score gradient class */
export function scoreGradientClass(score: number): string {
  if (score >= 70) return "score-gradient-high";
  if (score >= 40) return "score-gradient-medium";
  return "score-gradient-low";
}

/** SVG gradient def id for a score value (defs live in app/layout.tsx) */
export function scoreGradientId(score: number): string {
  if (score >= 70) return "scoreGradientHigh";
  if (score >= 40) return "scoreGradientMedium";
  return "scoreGradientLow";
}

/** Check if a CV file has a valid extension */
export function isValidCvFile(file: File): boolean {
  const ext = file.name.split(".").pop()?.toLowerCase();
  return ext === "pdf" || ext === "docx";
}

/** Max file size: 5 MB */
export const MAX_FILE_SIZE = 5 * 1024 * 1024;
