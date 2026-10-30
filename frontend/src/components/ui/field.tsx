import { useId, type InputHTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/cn";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  unit?: string;
  hint?: ReactNode;
  /** Message d'erreur déjà traduit (le backend renvoie un code). */
  error?: string;
  /** Élément à droite du champ (bouton afficher le mot de passe...). */
  end?: ReactNode;
};

/** Champ tactile : 48 px de haut, texte de 16 px sur mobile (pas de zoom iOS). */
export function Field({ label, unit, hint, error, end, className, id: idProp, ...rest }: Props) {
  const autoId = useId();
  const id = idProp ?? autoId;
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-label font-medium">
        {label}
      </label>
      <div
        className={cn(
          "flex h-12 items-center rounded-lg border bg-card transition-colors focus-within:border-fg focus-within:ring-2 focus-within:ring-line",
          error ? "border-loss" : "border-line",
        )}
      >
        <input
          id={id}
          {...rest}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className="h-full w-full min-w-0 rounded-lg bg-transparent px-3.5 text-input outline-none placeholder:text-muted sm:text-body"
        />
        {unit && <span className="px-3 text-small whitespace-nowrap text-muted">{unit}</span>}
        {end}
      </div>
      {error ? (
        <p id={`${id}-error`} className="animate-fade text-small text-loss">
          {error}
        </p>
      ) : (
        hint && (
          <div id={`${id}-hint`} className="text-small text-muted">
            {hint}
          </div>
        )
      )}
    </div>
  );
}
