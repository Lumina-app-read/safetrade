"use client";

import { CalendarDays, Coins, NotebookPen } from "lucide-react";
import { useState, type FormEvent } from "react";

import { usePolled } from "@/components/trading/use-live";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, SectionTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { useFormErrors } from "@/lib/use-form-errors";

import { AdminTitle, type ApiErr } from "./admin-ui";
import { planName } from "./admin-users";

type Plan = { code: string; price: string; currency: string; duration_days: number; active: boolean };
type Change = { at: string; plan: string; details: { before: Plan; after: Plan; note: string } };

/** Formules : prix, durée et disponibilité. Un changement ne touche jamais un abonnement payé. */
export function AdminPlans({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.adminPlans;
  const f = formatters(locale);
  const [version, setVersion] = useState(0);
  const data = usePolled<{ plans: Plan[]; changes: Change[] }>(`/admin/plans?v=${version}`, 0);

  return (
    <>
      <AdminTitle title={messages.admin.subscriptions} subtitle={t.subtitle} />
      <div className="mt-6">
        <Alert tone="info">{t.chariowNote}</Alert>
      </div>
      {data.error && !data.data && (
        <div className="mt-4">
          <Alert tone="error">{errorMessage(messages, data.error)}</Alert>
        </div>
      )}
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {data.data?.plans.map((plan) => (
          <PlanCard key={`${plan.code}-${version}`} plan={plan} locale={locale} messages={messages} onSaved={() => setVersion((v) => v + 1)} />
        ))}
      </div>

      <SectionTitle>{t.history}</SectionTitle>
      <Card className="p-2 sm:p-3">
        {data.data?.changes.length === 0 && <p className="p-3 text-muted">{t.noHistory}</p>}
        <ul className="divide-y divide-line">
          {data.data?.changes.map((change, index) => (
            <li key={`${change.at}-${index}`} className="px-2 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium">{planName(messages, change.plan)}</span>
                <span className="text-small text-muted">{f.dateTime(change.at)}</span>
              </div>
              <p className="mt-1 text-small text-muted">
                {interpolate(t.changeLine, {
                  before: `${f.money(Number(change.details.before.price), change.details.before.currency)} · ${interpolate(t.daysValue, { days: change.details.before.duration_days })}`,
                  after: `${f.money(Number(change.details.after.price), change.details.after.currency)} · ${interpolate(t.daysValue, { days: change.details.after.duration_days })}`,
                })}
              </p>
              <p className="mt-1 text-small">{change.details.note}</p>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}

function PlanCard({ plan, locale, messages, onSaved }: { plan: Plan; locale: Locale; messages: Messages; onSaved: () => void }) {
  const t = messages.adminPlans;
  const f = formatters(locale);
  const trial = plan.code === "trial";
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ApiErr | null>(null);
  const { field, validate } = useFormErrors({
    price: (value) => (/^\d{1,5}([.,]\d{1,2})?$/.test(value.trim()) ? undefined : t.priceInvalid),
    duration_days: (value) =>
      /^\d+$/.test(value.trim()) && Number(value) >= 1 && Number(value) <= 366 ? undefined : t.daysInvalid,
    note: (value) => (value.trim().length >= 5 ? undefined : messages.adminUi.noteInvalid),
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validate(event.currentTarget)) return;
    const form = new FormData(event.currentTarget);
    setPending(true);
    setFailure(null);
    const result = await api(`/admin/plans/${plan.code}`, {
      method: "PUT",
      body: {
        price: trial ? null : String(form.get("price")).trim().replace(",", "."),
        duration_days: Number(form.get("duration_days")),
        active: trial ? null : form.get("active") === "on",
        note: String(form.get("note")).trim(),
      },
    });
    setPending(false);
    if (!result.ok) return setFailure(result);
    onSaved();
  }

  return (
    <Card className="p-5 sm:p-6">
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-h3 font-medium">{planName(messages, plan.code)}</h2>
            <p className="mt-1 text-small text-muted">
              {trial ? t.free : f.money(Number(plan.price), plan.currency)} · {interpolate(t.daysValue, { days: plan.duration_days })}
            </p>
          </div>
          <Badge tone={plan.active ? "gain" : "neutral"}>{plan.active ? t.available : t.hidden}</Badge>
        </div>
        {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
        {!trial && (
          <Field
            label={interpolate(t.price, { currency: plan.currency })}
            icon={Coins}
            defaultValue={plan.price}
            inputMode="decimal"
            autoComplete="off"
            maxLength={8}
            {...field("price")}
          />
        )}
        <Field
          label={trial ? t.trialLength : t.length}
          icon={CalendarDays}
          defaultValue={String(plan.duration_days)}
          inputMode="numeric"
          autoComplete="off"
          maxLength={3}
          {...field("duration_days")}
        />
        {!trial && <Checkbox name="active" label={t.activeLabel} defaultChecked={plan.active} />}
        <Field
          label={messages.adminUi.note}
          icon={NotebookPen}
          placeholder={messages.adminUi.notePlaceholder}
          autoComplete="off"
          maxLength={300}
          {...field("note")}
        />
        <Button type="submit" variant="primary" size="lg" pending={pending} className="w-full sm:w-auto sm:self-start">
          {pending ? t.saving : t.save}
        </Button>
      </form>
    </Card>
  );
}
