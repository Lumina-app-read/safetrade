import { LOCALE_COOKIE, type Locale } from "./config";

const ONE_YEAR = 60 * 60 * 24 * 365;

/**
 * Mémorise la langue choisie, lue par src/proxy.ts pour les adresses sans préfixe.
 * L'enregistrement dans le profil arrivera avec les comptes (étape 1.8).
 */
export function rememberLocale(locale: Locale): void {
  document.cookie = `${LOCALE_COOKIE}=${locale}; path=/; max-age=${ONE_YEAR}; samesite=lax`;
}
