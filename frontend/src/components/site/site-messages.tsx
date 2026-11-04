"use client";

import { Info, TriangleAlert } from "lucide-react";

import type { Locale } from "@/i18n/config";
import { cn } from "@/lib/cn";
import { useSiteConfig } from "@/lib/site-config";

/** Bandeau d'annonce réglé dans l'administration ; rien n'est affiché sans annonce active. */
export function SiteAnnouncement({ locale, className }: { locale: Locale; className?: string }) {
  const announcement = useSiteConfig()?.announcement;
  if (!announcement) return null;
  const warning = announcement.tone === "warning";
  const Icon = warning ? TriangleAlert : Info;
  return (
    <div
      role="status"
      className={cn(
        "flex items-start justify-center gap-2 px-4 py-2.5 text-small sm:items-center",
        warning ? "bg-warn-soft text-warn" : "bg-accent-soft text-accent-text",
        className,
      )}
    >
      <Icon size={16} strokeWidth={1.5} aria-hidden className="mt-0.5 shrink-0 sm:mt-0" />
      <span>{announcement[locale]}</span>
    </div>
  );
}

/** Avertissement de risque : le texte de l'administration s'il existe, sinon celui des traductions. */
export function RiskWarning({ locale, fallback, className }: { locale: Locale; fallback: string; className?: string }) {
  const warning = useSiteConfig()?.risk_warning;
  return <p className={className}>{warning?.[locale] || fallback}</p>;
}
