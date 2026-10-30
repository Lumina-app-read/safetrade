import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

const TONES = {
  gain: "bg-gain-soft text-gain",
  loss: "bg-loss-soft text-loss",
  warn: "bg-warn-soft text-warn",
  // États neutres (bot en analyse, position ouverte) : jamais en rouge, pour ne pas évoquer une perte.
  neutral: "border border-line bg-card text-fg",
  brand: "bg-accent-soft text-accent-text",
} as const;

export type BadgeTone = keyof typeof TONES;

/** Pastille de statut : un point coloré et un libellé, la couleur ne porte jamais seule le sens. */
export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-small font-medium whitespace-nowrap",
        TONES[tone],
      )}
    >
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {children}
    </span>
  );
}
