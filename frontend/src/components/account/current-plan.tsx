"use client";

import { CreditCard } from "lucide-react";

import { useSession } from "@/components/shell/session";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { Messages } from "@/i18n/messages";

/** Libellé d'un niveau d'abonnement renvoyé par le backend. */
export function planLabel(messages: Messages, plan: string): string {
  const labels = messages.plans.levels as Record<string, string>;
  return labels[plan] ?? labels.none;
}

export function CurrentPlan({ messages }: { messages: Messages }) {
  const { user } = useSession();
  const active = user.subscription !== "none";
  return (
    <Card className="mt-6 flex items-center justify-between gap-4">
      <span className="flex min-w-0 items-center gap-3">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-page text-muted">
          <CreditCard size={20} strokeWidth={1.5} aria-hidden />
        </span>
        <span className="min-w-0">
          <span className="block text-small text-muted">{messages.plans.current}</span>
          <span className="block text-h3 font-medium">{planLabel(messages, user.subscription)}</span>
        </span>
      </span>
      <Badge tone={active ? "gain" : "neutral"}>{active ? messages.plans.active : messages.plans.inactive}</Badge>
    </Card>
  );
}
