"use client";

import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

import { applyTheme, readEffectiveTheme, subscribeTheme } from "@/lib/theme";

/**
 * Bouton unique de thème : l'icône montre le mode affiché (soleil en clair, lune en
 * sombre) et un clic passe à l'autre. Sans choix enregistré, le thème suit le système.
 */
export function ThemeToggle({ labels }: { labels: { switchToDark: string; switchToLight: string } }) {
  // Côté serveur, aucun mode n'est connu : l'icône apparaît à l'hydratation.
  const mode = useSyncExternalStore(subscribeTheme, readEffectiveTheme, () => null);
  const label = mode === "dark" ? labels.switchToLight : labels.switchToDark;

  return (
    <button
      type="button"
      onClick={() => applyTheme(mode === "dark" ? "light" : "dark")}
      aria-label={label}
      title={label}
      className="relative grid size-10 place-items-center overflow-hidden rounded-lg border border-line text-muted transition-colors hover:border-muted/60 hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
    >
      <Sun
        size={20}
        strokeWidth={1.5}
        aria-hidden
        className="absolute transition-all duration-300 data-[hidden=true]:scale-50 data-[hidden=true]:-rotate-90 data-[hidden=true]:opacity-0"
        data-hidden={mode !== "light"}
      />
      <Moon
        size={20}
        strokeWidth={1.5}
        aria-hidden
        className="absolute transition-all duration-300 data-[hidden=true]:scale-50 data-[hidden=true]:rotate-90 data-[hidden=true]:opacity-0"
        data-hidden={mode !== "dark"}
      />
    </button>
  );
}
