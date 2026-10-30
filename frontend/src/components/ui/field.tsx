import { useId, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  unit?: string;
  hint?: string;
  /** Message d'erreur déjà traduit (le backend renvoie un code). */
  error?: string;
};

export function Field({ label, unit, hint, error, className, ...rest }: Props) {
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-label font-medium">
        {label}
      </label>
      <div
        className={cn(
          "flex items-center rounded-lg border bg-page focus-within:border-accent",
          error ? "border-loss" : "border-line",
        )}
      >
        <input
          id={id}
          {...rest}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className="w-full min-w-0 bg-transparent px-3 py-2 outline-none"
        />
        {unit && <span className="px-3 text-small whitespace-nowrap text-muted">{unit}</span>}
      </div>
      {error ? (
        <p id={`${id}-error`} className="text-small text-loss">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="text-small text-muted">
            {hint}
          </p>
        )
      )}
    </div>
  );
}
