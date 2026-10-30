import { LoaderCircle } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

const VARIANTS = {
  // Action principale de page : anthracite (inversé en thème sombre).
  primary: "bg-primary text-on-primary hover:opacity-90",
  // Actions de trading : rouge de marque.
  accent: "bg-accent text-on-accent hover:bg-accent-hover",
  ghost: "border-line bg-card text-fg hover:bg-page",
  danger: "border-loss bg-card text-loss hover:bg-loss-soft",
} as const;

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof VARIANTS;
  icon?: ReactNode;
  /** Attente de la confirmation du backend : le bouton est bloqué, jamais de succès simulé. */
  pending?: boolean;
};

export function Button({ variant = "ghost", icon, pending = false, className, children, disabled, ...rest }: Props) {
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
      className={cn(
        "inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-transparent px-4 text-label font-medium whitespace-nowrap transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-55",
        VARIANTS[variant],
        className,
      )}
    >
      {pending ? <LoaderCircle size={20} strokeWidth={1.5} className="animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
}
