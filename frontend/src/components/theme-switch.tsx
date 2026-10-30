"use client";

import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { useSyncExternalStore } from "react";

import { applyTheme, DEFAULT_THEME, readTheme, subscribeTheme, THEMES, type Theme } from "@/lib/theme";

const ICONS: Record<Theme, LucideIcon> = { light: Sun, dark: Moon, auto: Monitor };

export function ThemeSwitch({ labels }: { labels: Record<Theme, string> }) {
  const theme = useSyncExternalStore(subscribeTheme, readTheme, () => DEFAULT_THEME);

  return (
    <div role="group" className="flex rounded-lg border border-line p-0.5">
      {THEMES.map((value) => {
        const Icon = ICONS[value];
        return (
          <button
            key={value}
            type="button"
            aria-pressed={theme === value}
            aria-label={labels[value]}
            title={labels[value]}
            onClick={() => applyTheme(value)}
            className="rounded-md p-1.5 text-muted hover:text-fg aria-pressed:bg-accent-soft aria-pressed:text-accent-text"
          >
            <Icon size={18} strokeWidth={1.5} aria-hidden />
          </button>
        );
      })}
    </div>
  );
}
