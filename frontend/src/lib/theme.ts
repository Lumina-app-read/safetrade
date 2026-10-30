export const THEMES = ["light", "dark", "auto"] as const;
export type Theme = (typeof THEMES)[number];

export const THEME_STORAGE_KEY = "st-theme";
export const DEFAULT_THEME: Theme = "auto";

export function isTheme(value: unknown): value is Theme {
  return typeof value === "string" && (THEMES as readonly string[]).includes(value);
}

/** Thème courant, lu sur l'attribut data-theme de <html> (source unique). */
export function readTheme(): Theme {
  const value = document.documentElement.dataset.theme;
  return isTheme(value) ? value : DEFAULT_THEME;
}

export function applyTheme(next: Theme): void {
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem(THEME_STORAGE_KEY, next);
  } catch {
    // Stockage indisponible (navigation privée) : le choix vaut pour la page.
  }
}

const DARK_QUERY = "(prefers-color-scheme: dark)";

/** Thème réellement affiché : « auto » est résolu avec la préférence du système. */
export function readEffectiveTheme(): "light" | "dark" {
  const theme = readTheme();
  if (theme !== "auto") return theme;
  return window.matchMedia(DARK_QUERY).matches ? "dark" : "light";
}

/** Prévient d'un changement de choix (attribut data-theme) ou du thème du système. */
export function subscribeTheme(onChange: () => void): () => void {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  const media = window.matchMedia(DARK_QUERY);
  media.addEventListener("change", onChange);
  return () => {
    observer.disconnect();
    media.removeEventListener("change", onChange);
  };
}

/**
 * Script exécuté avant le premier rendu : applique le thème enregistré pour
 * éviter tout flash. Le choix côté serveur (profil) s'y ajoutera à l'étape 1.8.
 */
export const themeInitScript = `(function(){try{var t=localStorage.getItem(${JSON.stringify(
  THEME_STORAGE_KEY,
)});if(${JSON.stringify(THEMES)}.indexOf(t)>-1)document.documentElement.dataset.theme=t;}catch(e){}})();`;
