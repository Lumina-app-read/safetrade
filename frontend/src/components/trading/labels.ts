import type { Messages } from "@/i18n/messages";

/**
 * Codes du moteur vers le texte traduit. Certains codes portent un détail venu de Deriv
 * (`order.refused_InvalidOfferings`) : le préfixe suffit pour l'expliquer.
 */
export function codeText(messages: Messages, code: string | null): string {
  const t = messages.trading.codes;
  if (!code) return "";
  const key = code.replace(/\./g, "_") as keyof typeof t;
  if (t[key]) return t[key];
  if (code.startsWith("order.refused")) return t.order_refused;
  if (code.startsWith("order.proposal")) return t.order_proposal;
  return t.unknown;
}

/** Nombre de décimales d'un cours, d'après le pas de cotation de Deriv. */
export function priceDecimals(pipSize: number): number {
  return Math.max(0, Math.round(-Math.log10(pipSize)));
}

/** Part de limite consommée, bornée entre 0 et 1 pour l'affichage. */
export function usage(value: number, limit: number): number {
  if (limit <= 0) return 0;
  return Math.min(1, Math.max(0, value / limit));
}
