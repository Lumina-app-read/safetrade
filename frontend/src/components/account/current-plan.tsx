import type { Messages } from "@/i18n/messages";

/** Libellé d'un niveau d'abonnement renvoyé par le backend. */
export function planLabel(messages: Messages, plan: string): string {
  const labels = messages.plans.levels as Record<string, string>;
  return labels[plan] ?? labels.none;
}
