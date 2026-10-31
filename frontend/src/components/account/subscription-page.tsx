"use client";

import { CalendarClock, Check, CreditCard, Hash, Phone, ReceiptText, UserRound } from "lucide-react";
import { useState, type FormEvent } from "react";

import { useSession } from "@/components/shell/session";
import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, SectionTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { useFormErrors } from "@/lib/use-form-errors";
import type { Rule } from "@/lib/validation";

import { usePolled } from "../trading/use-live";
import { planLabel } from "./current-plan";

type Plan = { code: string; duration_days: number; price: string; currency: string; providers: string[] };
type Order = { id: string; plan: string; amount: string; currency: string; status: string; created_at: string };
type Billing = {
  access: { status: string; plan: string; ends_at: string | null; allowed: boolean };
  plans: Plan[];
  orders: Order[];
};

const STATUS_TONES: Record<string, BadgeTone> = {
  trial: "gain",
  active: "gain",
  expired: "warn",
  suspended: "loss",
  none: "neutral",
};
const ORDER_TONES: Record<string, BadgeTone> = {
  paid: "gain",
  pending: "neutral",
  partial: "warn",
  failed: "loss",
  expired: "neutral",
  refunded: "neutral",
};

function PayForm({ plan, messages, onClose }: { plan: Plan; messages: Messages; onClose: () => void }) {
  const t = messages.plans;
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<{ code: string; retryAfter?: number } | null>(null);
  const rules: Record<string, Rule> = {
    last_name: (value) => (value.trim() ? undefined : t.lastNameRequired),
    phone_number: (value) => (/^\d{6,15}$/.test(value.replace(/[\s+]/g, "")) ? undefined : t.phoneInvalid),
    phone_country: (value) => (/^[a-zA-Z]{2}$/.test(value.trim()) ? undefined : t.countryInvalid),
  };
  const { field, validate } = useFormErrors(rules);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validate(event.currentTarget)) return;
    const form = new FormData(event.currentTarget);
    setPending(true);
    setFailure(null);
    const result = await api<{ checkout_url: string }>("/billing/checkout", {
      body: {
        plan: plan.code,
        last_name: String(form.get("last_name")).trim(),
        phone_number: String(form.get("phone_number")).replace(/[\s+]/g, ""),
        phone_country: String(form.get("phone_country")).trim().toUpperCase(),
      },
    });
    if (result.ok) {
      // L'accès ne s'active qu'à la confirmation du paiement par le fournisseur.
      window.location.assign(result.data.checkout_url);
      return;
    }
    setPending(false);
    setFailure(result);
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      <p className="text-muted">{t.payIntro}</p>
      {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
      <Field label={t.lastName} icon={UserRound} autoComplete="family-name" {...field("last_name")} />
      <Field label={t.phone} icon={Phone} placeholder={t.phonePlaceholder} inputMode="tel" autoComplete="tel" {...field("phone_number")} />
      <Field label={t.country} icon={Hash} placeholder={t.countryPlaceholder} maxLength={2} autoCapitalize="characters" autoComplete="country" {...field("phone_country")} />
      <Button type="submit" variant="accent" size="lg" pending={pending} className="w-full">
        {pending ? t.paying : t.payNow}
      </Button>
      <Button size="md" className="w-full" onClick={onClose}>
        {messages.trading.cancel}
      </Button>
    </form>
  );
}

/** Abonnement du client : statut calculé par le backend, paiement chez le fournisseur. */
export function SubscriptionPage({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.plans;
  const f = formatters(locale);
  const { user } = useSession();
  const billing = usePolled<Billing>("/billing/me", 15000);
  const [buying, setBuying] = useState<Plan | null>(null);
  const data = billing.data;
  const statuses = t.statuses as Record<string, string>;
  const orderStatuses = t.orderStatuses as Record<string, string>;
  const durations = t.durations as Record<string, string>;

  return (
    <div className="flex flex-col">
      <h1 className="text-h1">{messages.nav.subscription}</h1>
      {billing.error && !data && (
        <div className="mt-6">
          <Alert tone="error">{errorMessage(messages, billing.error)}</Alert>
        </div>
      )}
      {!data && !billing.error && <p className="mt-6 text-muted">{messages.trading.loading}</p>}
      {data && (
        <>
          <Card className="mt-6 flex flex-wrap items-center justify-between gap-4">
            <span className="flex min-w-0 items-center gap-3">
              <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-page text-muted">
                <CreditCard size={20} strokeWidth={1.5} aria-hidden />
              </span>
              <span className="min-w-0">
                <span className="block text-small text-muted">{t.current}</span>
                <span className="block text-h3 font-medium">{planLabel(messages, data.access.allowed ? data.access.plan : "none")}</span>
                {data.access.ends_at && (
                  <span className="flex items-center gap-1.5 text-small text-muted">
                    <CalendarClock size={14} strokeWidth={1.5} aria-hidden />
                    {interpolate(data.access.allowed ? t.endsOn : t.endedOn, { date: f.dateTime(data.access.ends_at) })}
                  </span>
                )}
              </span>
            </span>
            <Badge tone={STATUS_TONES[data.access.status] ?? "neutral"}>{statuses[data.access.status] ?? statuses.none}</Badge>
          </Card>

          {!data.access.allowed && (
            <div className="mt-4">
              <Alert tone="info">{t.blocked}</Alert>
            </div>
          )}

          <SectionTitle>{t.choose}</SectionTitle>
          <div className="grid gap-3 sm:grid-cols-3">
            {data.plans.map((plan) => (
              <Card key={plan.code} className="flex flex-col gap-3 p-5">
                <div>
                  <h2 className="text-h3 font-medium">{planLabel(messages, plan.code)}</h2>
                  <p className="text-small text-muted">{durations[plan.code]}</p>
                </div>
                <p className="text-kpi font-medium tabular-nums">{f.money(Number(plan.price), plan.currency)}</p>
                <ul className="flex flex-col gap-1.5 text-small text-muted">
                  <li className="flex items-center gap-1.5">
                    <Check size={14} strokeWidth={1.5} aria-hidden className="shrink-0 text-gain" />
                    {t.featureBot}
                  </li>
                  <li className="flex items-center gap-1.5">
                    <Check size={14} strokeWidth={1.5} aria-hidden className="shrink-0 text-gain" />
                    {t.featureManual}
                  </li>
                </ul>
                <Button variant="primary" size="lg" className="mt-auto w-full" disabled={!plan.providers.includes("chariow")} onClick={() => setBuying(plan)}>
                  {data.access.status === "active" ? t.extend : t.subscribe}
                </Button>
              </Card>
            ))}
          </div>
          <p className="mt-3 text-small text-muted">{t.localCurrency}</p>
          {data.plans.some((plan) => plan.providers.length === 0) && <p className="mt-1 text-small text-muted">{t.paymentSoon}</p>}

          <SectionTitle>{t.orders}</SectionTitle>
          <Card className="p-4 sm:p-5">
            {data.orders.length === 0 ? (
              <p className="flex items-center gap-2 text-muted">
                <ReceiptText size={18} strokeWidth={1.5} aria-hidden />
                {t.noOrders}
              </p>
            ) : (
              <ul className="flex flex-col">
                {data.orders.map((order) => (
                  <li key={order.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-line py-3 last:border-b-0">
                    <span className="min-w-0">
                      <span className="block font-medium">{planLabel(messages, order.plan)}</span>
                      <span className="block text-small text-muted">{f.dateTime(order.created_at)}</span>
                    </span>
                    <span className="flex items-center gap-3">
                      <span className="font-medium tabular-nums">{f.money(Number(order.amount), order.currency)}</span>
                      <Badge tone={ORDER_TONES[order.status] ?? "neutral"}>{orderStatuses[order.status] ?? order.status}</Badge>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
      <Dialog open={buying !== null} onClose={() => setBuying(null)} title={buying ? planLabel(messages, buying.code) : user.first_name} closeLabel={messages.trading.close}>
        {buying && <PayForm plan={buying} messages={messages} onClose={() => setBuying(null)} />}
      </Dialog>
    </div>
  );
}
