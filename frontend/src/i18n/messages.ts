import en from "@/messages/en.json";
import fr from "@/messages/fr.json";

import type { Locale } from "./config";

export type Messages = typeof fr;

// Le typage impose à chaque langue la structure du français ; le contrôle
// scripts/check-messages.mjs bloque en plus le build si une clé manque ou est vide.
const MESSAGES: Record<Locale, Messages> = { fr, en };

export function getMessages(locale: Locale): Messages {
  return MESSAGES[locale];
}

/** Remplace les variables « {nom} » d'un texte traduit. */
export function interpolate(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in values ? String(values[name]) : match,
  );
}
