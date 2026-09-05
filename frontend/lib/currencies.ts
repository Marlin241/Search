/** Devises supportées pour l'attente salariale du candidat - liste
 * volontairement restreinte aux marchés réellement en jeu, pas la liste
 * ISO 4217 complète. Garder en phase avec _SUPPORTED_CURRENCIES côté
 * backend (app/schemas/candidate_profile.py). */
export interface CurrencyOption {
  code: string;
  label: string;
}

export const SUPPORTED_CURRENCIES: CurrencyOption[] = [
  { code: "XOF", label: "FCFA - Afrique de l'Ouest (XOF)" },
  { code: "XAF", label: "FCFA - Afrique centrale (XAF)" },
  { code: "EUR", label: "Euro (EUR)" },
  { code: "USD", label: "Dollar US (USD)" },
];

export const DEFAULT_CURRENCY = "XOF";

export function currencyLabel(code: string | null | undefined): string {
  return SUPPORTED_CURRENCIES.find((c) => c.code === code)?.label ?? code ?? DEFAULT_CURRENCY;
}
