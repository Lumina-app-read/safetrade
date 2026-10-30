import en from "@/messages/en.json";
import fr from "@/messages/fr.json";

// Le mécanisme complet (choix de la langue, préfixes /fr et /en) arrive à l'étape 1.3.
export const LOCALES = ["fr", "en"] as const;
export type Locale = (typeof LOCALES)[number];
export type Messages = typeof fr;

const MESSAGES: Record<Locale, Messages> = { fr, en };

export function getMessages(locale: Locale): Messages {
  return MESSAGES[locale];
}
