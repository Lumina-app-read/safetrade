import { ShieldCheck } from "lucide-react";

import { cn } from "@/lib/cn";

/**
 * Logo provisoire : pictogramme rouge et mot-symbole « Safe » anthracite, « Trade » rouge,
 * comme le logo source (docs/brand). À remplacer par le fichier vectoriel officiel.
 * onDark : sur fond anthracite, le mot entier en clair (le rouge y serait peu lisible en petit).
 */
export function Logo({
  className,
  compact = false,
  onDark = false,
}: {
  className?: string;
  compact?: boolean;
  onDark?: boolean;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-h3 font-medium", className)}>
      <span className="grid size-8 place-items-center rounded-lg bg-accent text-on-accent shadow-[0_0_24px_var(--brand-ring)]">
        <ShieldCheck size={20} strokeWidth={1.5} aria-hidden />
      </span>
      <span className={cn(compact && "max-sm:sr-only")}>
        Safe<span className={onDark ? undefined : "text-accent-text"}>Trade</span>
      </span>
    </span>
  );
}
