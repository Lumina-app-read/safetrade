/**
 * Réglages publics du site (GET /site/config), lus une fois par page et partagés entre les
 * composants. Le serveur décide ; une erreur de lecture laisse les textes par défaut.
 */

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

export type SiteConfig = {
  deriv_signup_url: string | null;
  announcement: { enabled: boolean; tone: "info" | "warning"; fr: string; en: string } | null;
  risk_warning: { fr: string; en: string } | null;
  legal: string[];
};

let pending: Promise<SiteConfig | null> | null = null;

export function readSiteConfig(): Promise<SiteConfig | null> {
  pending ??= api<SiteConfig>("/site/config").then((result) => (result.ok ? result.data : null));
  return pending;
}

export function useSiteConfig(): SiteConfig | null {
  const [config, setConfig] = useState<SiteConfig | null>(null);
  useEffect(() => {
    let active = true;
    void readSiteConfig().then((value) => {
      if (active) setConfig(value);
    });
    return () => {
      active = false;
    };
  }, []);
  return config;
}
