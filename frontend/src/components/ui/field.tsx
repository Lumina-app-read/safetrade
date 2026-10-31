import { CircleAlert, type LucideIcon } from "lucide-react";
import { useId, type InputHTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/cn";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  /** Icône Lucide en tête du champ ; elle prend la couleur de marque au focus. */
  icon?: LucideIcon;
  unit?: string;
  hint?: ReactNode;
  /** Message d'erreur déjà traduit (le backend renvoie un code). */
  error?: string;
  /** Élément à droite du champ (bouton afficher le mot de passe...). */
  end?: ReactNode;
};

/**
 * Champ tactile : 48 px de haut, texte de 16 px sur mobile (pas de zoom iOS).
 * Focus : bordure rouge de marque et halo léger.
 */
export function Field({ label, icon: Icon, unit, hint, error, end, className, id: idProp, ...rest }: Props) {
  const autoId = useId();
  const id = idProp ?? autoId;
  const describedBy = [error && `${id}-error`, hint && `${id}-hint`].filter(Boolean).join(" ") || undefined;
  return (
    <div data-field className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-label font-medium">
        {label}
      </label>
      <div
        className={cn(
          "group flex h-12 items-center rounded-lg border bg-card transition-[border-color,box-shadow] duration-200",
          "focus-within:ring-[3px]",
          error
            ? "border-loss focus-within:ring-loss/15"
            : "border-line hover:border-muted/60 focus-within:border-accent focus-within:ring-accent/15",
        )}
      >
        {Icon && (
          <Icon
            size={20}
            strokeWidth={1.5}
            aria-hidden
            className={cn(
              "ml-3.5 shrink-0 transition-colors duration-200",
              error ? "text-loss" : "text-muted group-focus-within:text-accent-text",
            )}
          />
        )}
        <input
          id={id}
          {...rest}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cn(
            "h-full w-full min-w-0 rounded-lg bg-transparent pr-3.5 text-input outline-none placeholder:text-muted/70 sm:text-body",
            Icon ? "pl-2.5" : "pl-3.5",
          )}
        />
        {unit && <span className="px-3 text-small whitespace-nowrap text-muted">{unit}</span>}
        {end}
      </div>
      {error && (
        <p id={`${id}-error`} aria-live="polite" className="flex animate-fade items-start gap-1.5 text-small text-loss">
          <CircleAlert size={14} strokeWidth={1.5} aria-hidden className="mt-0.5 shrink-0" />
          {error}
        </p>
      )}
      {hint && (
        <div id={`${id}-hint`} className="text-small text-muted">
          {hint}
        </div>
      )}
    </div>
  );
}
