import { TrendingDown, TrendingUp } from "lucide-react";

import { cn } from "@/lib/cn";

/**
 * Montant de gain ou de perte : couleur, signe et icône ensemble,
 * jamais la couleur seule (section 15). Le texte est déjà formaté selon la langue.
 */
export function SignedAmount({ value, formatted }: { value: number; formatted: string }) {
  if (value === 0) return <span className="tabular-nums">{formatted}</span>;
  const up = value > 0;
  const Icon = up ? TrendingUp : TrendingDown;
  return (
    <span className={cn("inline-flex items-center gap-1 tabular-nums", up ? "text-gain" : "text-loss")}>
      <Icon size={16} strokeWidth={1.5} aria-hidden />
      {up ? "+" : ""}
      {formatted}
    </span>
  );
}
