import { Check, Circle } from "lucide-react";

import type { Messages } from "@/i18n/messages";
import { cn } from "@/lib/cn";
import { PASSWORD_RULES } from "@/lib/validation";

type Props = {
  password: string;
  labels: Messages["auth"]["register"];
  /** Après une erreur : les règles non remplies passent en rouge. */
  invalid?: boolean;
};

export function PasswordRules({ password, labels, invalid = false }: Props) {
  return (
    <ul className="mt-0.5 flex flex-col gap-1">
      {PASSWORD_RULES.map(({ key, test }) => {
        const ok = test(password);
        const Icon = ok ? Check : Circle;
        return (
          <li key={key} className={cn("flex items-center gap-2 transition-colors", ok ? "text-gain" : invalid && "text-loss")}>
            <Icon size={14} strokeWidth={ok ? 2 : 1.5} aria-hidden />
            {labels[key]}
          </li>
        );
      })}
    </ul>
  );
}
