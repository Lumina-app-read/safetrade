import { Check } from "lucide-react";
import { useId, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label: string;
  /** Message d'erreur déjà traduit. */
  error?: string;
};

/** Case à cocher : cible tactile de 44 px, case visuelle de 20 px aux couleurs de la marque. */
export function Checkbox({ label, error, className, id: idProp, ...rest }: Props) {
  const autoId = useId();
  const id = idProp ?? autoId;
  return (
    <div className={className}>
      <label htmlFor={id} className="flex min-h-11 cursor-pointer items-center gap-2.5">
        <input
          id={id}
          type="checkbox"
          {...rest}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          className="peer sr-only"
        />
        <span
          aria-hidden
          className={cn(
            "grid size-5 shrink-0 place-items-center rounded-md border bg-card text-transparent transition-colors",
            "peer-checked:border-accent peer-checked:bg-accent peer-checked:text-on-accent",
            "peer-focus-visible:ring-[3px] peer-focus-visible:ring-accent/15",
            error ? "border-loss" : "border-muted/60",
          )}
        >
          <Check size={14} strokeWidth={2.5} />
        </span>
        <span className="text-label">{label}</span>
      </label>
      {error && (
        <p id={`${id}-error`} className="animate-fade pl-7.5 text-small text-loss">
          {error}
        </p>
      )}
    </div>
  );
}
