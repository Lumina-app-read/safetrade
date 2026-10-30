import { CircleAlert, CircleCheck, Info, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

const TONES: Record<"error" | "success" | "info", { box: string; icon: LucideIcon }> = {
  error: { box: "border-loss/40 bg-loss-soft text-fg", icon: CircleAlert },
  success: { box: "border-gain/40 bg-gain-soft text-fg", icon: CircleCheck },
  info: { box: "border-line bg-page text-fg", icon: Info },
};

/** Message contextuel annoncé aux lecteurs d'écran (role alert ou status). */
export function Alert({ tone, children }: { tone: keyof typeof TONES; children: ReactNode }) {
  const { box, icon: Icon } = TONES[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn("flex animate-rise items-start gap-3 rounded-lg border p-3.5 text-body", box)}
    >
      <Icon
        size={20}
        strokeWidth={1.5}
        aria-hidden
        className={cn("mt-px shrink-0", tone === "error" ? "text-loss" : tone === "success" ? "text-gain" : "text-muted")}
      />
      <div>{children}</div>
    </div>
  );
}
