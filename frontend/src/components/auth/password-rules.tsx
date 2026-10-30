import { Check, Circle } from "lucide-react";

import type { Messages } from "@/i18n/messages";
import { cn } from "@/lib/cn";

// Règles affichées en direct ; le serveur reste seul juge (mêmes seuils côté backend).
const RULES = [
  { key: "ruleLength", test: (p: string) => p.length >= 10 },
  { key: "ruleVariety", test: (p: string) => new Set(p).size >= 4 },
] as const;

export function PasswordRules({ password, labels }: { password: string; labels: Messages["auth"]["register"] }) {
  return (
    <ul className="mt-0.5 flex flex-col gap-1">
      {RULES.map(({ key, test }) => {
        const ok = test(password);
        const Icon = ok ? Check : Circle;
        return (
          <li key={key} className={cn("flex items-center gap-2 transition-colors", ok && "text-gain")}>
            <Icon size={14} strokeWidth={ok ? 2 : 1.5} aria-hidden />
            {labels[key]}
          </li>
        );
      })}
    </ul>
  );
}
