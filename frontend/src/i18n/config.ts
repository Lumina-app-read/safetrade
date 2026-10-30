// Langues autorisées : français et anglais uniquement (section 15). Ajouter une
// langue = ajouter son code ici et son fichier dans src/messages, sans autre changement.
export const LOCALES = ["fr", "en"] as const;
export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "fr";
export const LOCALE_COOKIE = "st-locale";

/** Code BCP 47 complet utilisé par Intl pour les nombres, dates et devises. */
export const INTL_LOCALE: Record<Locale, string> = { fr: "fr-FR", en: "en-US" };

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

/**
 * Choisit la langue d'après l'en-tête Accept-Language (« fr-CA,fr;q=0.9,en;q=0.8 »).
 * Les langues sont triées par poids q ; la première supportée l'emporte.
 */
export function negotiateLocale(acceptLanguage: string | null | undefined): Locale {
  if (!acceptLanguage) return DEFAULT_LOCALE;
  const ranked = acceptLanguage
    .split(",")
    .map((part, index) => {
      const [tag = "", ...params] = part.trim().split(";");
      const q = params.map((p) => p.trim()).find((p) => p.startsWith("q="));
      const weight = q ? Number.parseFloat(q.slice(2)) : 1;
      return { base: tag.toLowerCase().split("-")[0], weight: Number.isNaN(weight) ? 0 : weight, index };
    })
    .filter((entry) => entry.weight > 0)
    .sort((a, b) => b.weight - a.weight || a.index - b.index);
  return ranked.map((entry) => entry.base).find(isLocale) ?? DEFAULT_LOCALE;
}
