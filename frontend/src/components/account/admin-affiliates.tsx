"use client";

import { Hash, Pencil, Percent, StickyNote, TimerReset, UserPlus, Users } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { useAdmin } from "@/components/shell/admin-shell";
import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, SectionTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useFormErrors } from "@/lib/use-form-errors";

import { usePolled } from "../trading/use-live";
import { planLabel } from "./current-plan";

type Program = { rate_pct: string; recurring: boolean; attribution_days: number; hold_days: number };
type Totals = { referrals: number; converted: number; held: string; available: string; paid: string; currency: string };
type Row = {
  id: string;
  email: string;
  first_name: string;
  status: string;
  code: string | null;
  message: string;
  payout_details: string;
  review_note: string | null;
  created_at: string;
  totals: Totals;
};
type Referral = { id: string; email: string; status: string; reason: string | null; attributed_at: string };
type Commission = {
  id: string;
  plan: string;
  base_amount: string;
  rate_pct: string;
  amount: string;
  currency: string;
  status: string;
  reason: string | null;
  available_at: string;
};
type Payout = { id: string; amount: string; currency: string; method: string; reference: string; paid_at: string };
type Detail = Row & { referrals: Referral[]; commissions: Commission[]; payouts: Payout[] };
type Failure = { code: string; retryAfter?: number };

const STATUS_TONES: Record<string, BadgeTone> = { pending: "brand", approved: "gain", refused: "neutral", suspended: "warn" };
const REFERRAL_TONES: Record<string, BadgeTone> = { active: "gain", review: "warn", blocked: "loss" };
const COMMISSION_TONES: Record<string, BadgeTone> = {
  held: "neutral",
  review: "warn",
  available: "gain",
  paid: "gain",
  cancelled: "neutral",
};
const FILTERS = ["", "pending", "approved", "refused", "suspended"] as const;
const METHODS = ["mobile_money", "crypto", "bank", "other"] as const;
const ROW = "flex flex-wrap items-center justify-between gap-2 border-b border-line py-3 last:border-b-0";

function ProgramForm({ program, messages, onSaved }: { program: Program; messages: Messages; onSaved: () => void }) {
  const t = messages.affiliate.admin;
  const [recurring, setRecurring] = useState(program.recurring);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const days = (value: string) => (/^\d{1,3}$/.test(value.trim()) && Number(value) <= 365 ? undefined : t.daysInvalid);
  const { field, validate } = useFormErrors({
    rate_pct: (value) => {
      const rate = Number(value.replace(",", "."));
      return rate > 0 && rate <= 100 ? undefined : t.rateInvalid;
    },
    attribution_days: (value) => days(value) ?? (Number(value) >= 1 ? undefined : t.daysInvalid),
    hold_days: days,
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validate(event.currentTarget)) return;
    const form = new FormData(event.currentTarget);
    setPending(true);
    setFailure(null);
    const result = await api("/admin/affiliates/program", {
      method: "PUT",
      body: {
        rate_pct: String(form.get("rate_pct")).replace(",", ".").trim(),
        recurring,
        attribution_days: Number(form.get("attribution_days")),
        hold_days: Number(form.get("hold_days")),
      },
    });
    setPending(false);
    if (result.ok) onSaved();
    else setFailure(result);
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
      <Field label={t.rate} icon={Percent} unit="%" inputMode="decimal" defaultValue={program.rate_pct} {...field("rate_pct")} />
      <Field label={t.window} icon={UserPlus} unit={t.days} inputMode="numeric" defaultValue={program.attribution_days} {...field("attribution_days")} />
      <Field label={t.hold} icon={TimerReset} unit={t.days} inputMode="numeric" defaultValue={program.hold_days} {...field("hold_days")} />
      <Checkbox label={t.recurring} checked={recurring} onChange={(e) => setRecurring(e.target.checked)} />
      <Button type="submit" variant="primary" size="lg" pending={pending} className="w-full">
        {pending ? t.saving : t.save}
      </Button>
    </form>
  );
}

function PayoutForm({
  detail,
  messages,
  locale,
  onDone,
}: {
  detail: Detail;
  messages: Messages;
  locale: Locale;
  onDone: (next: Detail) => void;
}) {
  const t = messages.affiliate.admin;
  const f = formatters(locale);
  const methods = messages.affiliate.methods as Record<string, string>;
  const [method, setMethod] = useState<(typeof METHODS)[number]>("mobile_money");
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const { field, validate } = useFormErrors({
    reference: (value) => (value.trim().length >= 3 ? undefined : t.referenceInvalid),
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validate(event.currentTarget)) return;
    const reference = String(new FormData(event.currentTarget).get("reference")).trim();
    setPending(true);
    setFailure(null);
    const result = await api<Detail>(`/admin/affiliates/${detail.id}/payouts`, { body: { method, reference } });
    setPending(false);
    if (result.ok) onDone(result.data);
    else setFailure(result);
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-3">
      <p className="font-medium">{interpolate(t.payoutAmount, { amount: f.money(Number(detail.totals.available), detail.totals.currency) })}</p>
      <p className="text-small text-muted">{t.payoutNote}</p>
      {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
      <div role="group" aria-label={t.method} className="grid grid-cols-2 gap-2">
        {METHODS.map((value) => (
          <Button key={value} size="lg" aria-pressed={method === value} variant={method === value ? "primary" : "ghost"} onClick={() => setMethod(value)}>
            {methods[value]}
          </Button>
        ))}
      </div>
      <Field label={t.reference} icon={Hash} placeholder={t.referencePlaceholder} maxLength={120} autoComplete="off" {...field("reference")} />
      <Button type="submit" variant="primary" size="lg" pending={pending} className="w-full">
        {t.payoutSubmit}
      </Button>
    </form>
  );
}

function DetailPanel({
  id,
  locale,
  messages,
  onChanged,
}: {
  id: string;
  locale: Locale;
  messages: Messages;
  onChanged: () => void;
}) {
  const t = messages.affiliate.admin;
  const f = formatters(locale);
  const { permissions } = useAdmin();
  const canWrite = permissions.includes("affiliates.write");
  const canPay = permissions.includes("payouts.write");
  const statuses = t.statuses as Record<string, string>;
  const referralStatuses = t.referralStatuses as Record<string, string>;
  const commissionStatuses = messages.affiliate.commissionStatuses as Record<string, string>;
  const reasons = t.reasons as Record<string, string>;
  const methods = messages.affiliate.methods as Record<string, string>;
  const [detail, setDetail] = useState<Detail | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState("");

  useEffect(() => {
    let active = true;
    api<Detail>(`/admin/affiliates/${id}`).then((result) => {
      if (!active) return;
      if (result.ok) setDetail(result.data);
      else setFailure(result);
    });
    return () => {
      active = false;
    };
  }, [id]);

  async function act(path: string, body?: object) {
    setBusy(path);
    setFailure(null);
    const result = await api<Detail>(`/admin/affiliates/${path}`, body ? { body } : { method: "POST" });
    setBusy(null);
    if (result.ok) {
      setDetail(result.data);
      setNote("");
      onChanged();
    } else setFailure(result);
  }

  if (!detail) {
    return failure ? <Alert tone="error">{errorMessage(messages, failure)}</Alert> : <p className="text-muted">{messages.trading.loading}</p>;
  }
  const review = (action: string) => act(`${id}/${action}`, { note: note.trim() || null });
  const reviewable = detail.status === "pending" || detail.status === "approved" || detail.status === "suspended";

  return (
    <div className="flex flex-col gap-4">
      {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="min-w-0">
          <span className="block font-medium break-all">{detail.email}</span>
          <span className="block text-small text-muted">{detail.code ?? t.noCode}</span>
        </span>
        <Badge tone={STATUS_TONES[detail.status] ?? "neutral"}>{statuses[detail.status] ?? detail.status}</Badge>
      </div>
      <dl className="flex flex-col gap-2">
        <div>
          <dt className="text-small text-muted">{t.application}</dt>
          <dd className="break-words">{detail.message}</dd>
        </div>
        <div>
          <dt className="text-small text-muted">{t.payoutDetails}</dt>
          <dd className="break-words">{detail.payout_details}</dd>
        </div>
        {detail.review_note && (
          <div>
            <dt className="text-small text-muted">{t.note}</dt>
            <dd className="break-words">{detail.review_note}</dd>
          </div>
        )}
      </dl>

      {canWrite && reviewable && (
        <div className="flex flex-col gap-3 border-t border-line pt-4">
          <Field label={t.note} icon={StickyNote} maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="flex flex-wrap gap-2">
            {detail.status === "pending" && (
              <>
                <Button variant="primary" size="lg" pending={busy === `${id}/approve`} onClick={() => review("approve")}>
                  {t.approve}
                </Button>
                <Button variant="danger" size="lg" pending={busy === `${id}/refuse`} onClick={() => review("refuse")}>
                  {t.refuse}
                </Button>
              </>
            )}
            {detail.status === "approved" && (
              <Button variant="danger" size="lg" pending={busy === `${id}/suspend`} onClick={() => review("suspend")}>
                {t.suspend}
              </Button>
            )}
            {detail.status === "suspended" && (
              <Button variant="primary" size="lg" pending={busy === `${id}/approve`} onClick={() => review("approve")}>
                {t.reinstate}
              </Button>
            )}
          </div>
        </div>
      )}

      <h3 className="mt-2 text-h3 font-medium">{t.referrals}</h3>
      {detail.referrals.length === 0 ? (
        <p className="text-muted">{messages.affiliate.noReferrals}</p>
      ) : (
        <ul className="flex flex-col">
          {detail.referrals.map((row) => (
            <li key={row.id} className={ROW}>
              <span className="min-w-0">
                <span className="block break-all">{row.email}</span>
                <span className="block text-small text-muted">
                  {f.date(row.attributed_at)}
                  {row.reason ? ` · ${reasons[row.reason] ?? row.reason}` : ""}
                </span>
              </span>
              <Badge tone={REFERRAL_TONES[row.status] ?? "neutral"}>{referralStatuses[row.status] ?? row.status}</Badge>
            </li>
          ))}
        </ul>
      )}

      <h3 className="mt-2 text-h3 font-medium">{t.commissions}</h3>
      {detail.commissions.length === 0 ? (
        <p className="text-muted">{messages.affiliate.noCommissions}</p>
      ) : (
        <ul className="flex flex-col">
          {detail.commissions.map((row) => (
            <li key={row.id} className={cn(ROW, "flex-col items-stretch")}>
              <span className="flex flex-wrap items-center justify-between gap-2">
                <span className="min-w-0">
                  <span className="block font-medium">
                    {f.money(Number(row.amount), row.currency)} · {planLabel(messages, row.plan)}
                  </span>
                  <span className="block text-small text-muted">
                    {interpolate(messages.affiliate.availableOn, { date: f.date(row.available_at) })}
                    {row.reason ? ` · ${reasons[row.reason] ?? row.reason}` : ""}
                  </span>
                </span>
                <Badge tone={COMMISSION_TONES[row.status] ?? "neutral"}>{commissionStatuses[row.status] ?? row.status}</Badge>
              </span>
              {canWrite && (row.status === "held" || row.status === "review" || row.status === "available") && (
                <span className="mt-2 flex flex-wrap gap-2">
                  {row.status === "review" && (
                    <Button pending={busy === `commissions/${row.id}/release`} onClick={() => act(`commissions/${row.id}/release`)}>
                      {t.release}
                    </Button>
                  )}
                  <Button variant="danger" pending={busy === `commissions/${row.id}/cancel`} onClick={() => act(`commissions/${row.id}/cancel`)}>
                    {t.cancel}
                  </Button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      <h3 className="mt-2 text-h3 font-medium">{t.payouts}</h3>
      {detail.payouts.length === 0 ? (
        <p className="text-muted">{messages.affiliate.noPayouts}</p>
      ) : (
        <ul className="flex flex-col">
          {detail.payouts.map((row) => (
            <li key={row.id} className={ROW}>
              <span className="min-w-0">
                <span className="block font-medium">{f.money(Number(row.amount), row.currency)}</span>
                <span className="block text-small break-all text-muted">
                  {methods[row.method] ?? row.method} · {row.reference} · {f.date(row.paid_at)}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
      {canPay && detail.status === "approved" &&
        (Number(detail.totals.available) > 0 ? (
          <PayoutForm
            key={detail.totals.available}
            detail={detail}
            messages={messages}
            locale={locale}
            onDone={(next) => {
              setDetail(next);
              onChanged();
            }}
          />
        ) : (
          <p className="text-small text-muted">{t.payoutNothing}</p>
        ))}
    </div>
  );
}

/** Demandes, barème, commissions et versements. Chaque droit est revérifié par le backend. */
export function AdminAffiliates({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.affiliate.admin;
  const f = formatters(locale);
  const { permissions } = useAdmin();
  const canRead = permissions.includes("affiliates.read");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("");
  const [editing, setEditing] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const list = usePolled<{ affiliates: Row[] }>(canRead ? `/admin/affiliates${filter ? `?status=${filter}` : ""}` : null, 30000);
  const program = usePolled<Program>(canRead ? "/admin/affiliates/program" : null, 0);
  const reload = list.reload;
  const onChanged = useCallback(() => reload(), [reload]);
  const statuses = t.statuses as Record<string, string>;
  const rules = program.data;
  const rows = list.data?.affiliates;
  const opened = rows?.find((row) => row.id === openId);

  if (!canRead) {
    return (
      <>
        <h1 className="text-h1">{t.title}</h1>
        <div className="mt-6">
          <Alert tone="error">{messages.admin.deniedBody}</Alert>
        </div>
      </>
    );
  }

  return (
    <>
      <h1 className="text-h1">{t.title}</h1>
      <p className="mt-1 text-muted">{t.subtitle}</p>

      <SectionTitle>{t.program}</SectionTitle>
      <Card className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
        {rules ? (
          <dl className="grid w-full flex-1 grid-cols-2 gap-4 lg:grid-cols-4">
            <div>
              <dt className="text-small text-muted">{t.rate}</dt>
              <dd className="font-medium">{f.percent(Number(rules.rate_pct) / 100, Number.isInteger(Number(rules.rate_pct)) ? 0 : 2)}</dd>
            </div>
            <div>
              <dt className="text-small text-muted">{t.base}</dt>
              <dd className="font-medium">{rules.recurring ? t.basisRecurring : t.basisFirst}</dd>
            </div>
            <div>
              <dt className="text-small text-muted">{t.window}</dt>
              <dd className="font-medium">{interpolate(t.daysValue, { days: rules.attribution_days })}</dd>
            </div>
            <div>
              <dt className="text-small text-muted">{t.hold}</dt>
              <dd className="font-medium">{interpolate(t.daysValue, { days: rules.hold_days })}</dd>
            </div>
          </dl>
        ) : (
          <p className="text-muted">{messages.trading.loading}</p>
        )}
        {rules && permissions.includes("settings.write") && (
          <Button size="lg" className="w-full sm:w-auto" onClick={() => setEditing(true)}>
            <Pencil size={18} strokeWidth={1.5} aria-hidden />
            {t.edit}
          </Button>
        )}
      </Card>

      <SectionTitle>{t.applications}</SectionTitle>
      <div role="group" aria-label={t.filterLabel} className="mb-3 flex gap-2 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {FILTERS.map((value) => (
          <Button key={value || "all"} size="lg" className="shrink-0" variant={filter === value ? "primary" : "ghost"} aria-pressed={filter === value} onClick={() => setFilter(value)}>
            {value ? statuses[value] : t.filterAll}
          </Button>
        ))}
      </div>
      {list.error && !rows && <Alert tone="error">{errorMessage(messages, list.error)}</Alert>}
      {!rows && !list.error && <p className="text-muted">{messages.trading.loading}</p>}
      {rows?.length === 0 && (
        <Card className="p-4 sm:p-5">
          <p className="flex items-center gap-2 text-muted">
            <Users size={18} strokeWidth={1.5} aria-hidden />
            {t.empty}
          </p>
        </Card>
      )}
      {rows && rows.length > 0 && (
        <ul className="grid gap-3 md:grid-cols-2">
          {rows.map((row) => (
            <li key={row.id}>
              <Card className="flex h-full flex-col gap-3 p-4 sm:p-5">
                <div className="flex items-start justify-between gap-2">
                  <span className="min-w-0">
                    <span className="block font-medium">{row.first_name}</span>
                    <span className="block text-small break-all text-muted">{row.email}</span>
                  </span>
                  <Badge tone={STATUS_TONES[row.status] ?? "neutral"}>{statuses[row.status] ?? row.status}</Badge>
                </div>
                <dl className="grid grid-cols-3 gap-2">
                  <div className="min-w-0">
                    <dt className="truncate text-small text-muted">{messages.affiliate.referrals}</dt>
                    <dd className="font-medium tabular-nums">{f.number(row.totals.referrals)}</dd>
                  </div>
                  <div className="min-w-0">
                    <dt className="truncate text-small text-muted">{messages.affiliate.held}</dt>
                    <dd className="font-medium tabular-nums">{f.moneyShort(Number(row.totals.held), row.totals.currency)}</dd>
                  </div>
                  <div className="min-w-0">
                    <dt className="truncate text-small text-muted">{messages.affiliate.available}</dt>
                    <dd className="font-medium tabular-nums">{f.moneyShort(Number(row.totals.available), row.totals.currency)}</dd>
                  </div>
                </dl>
                <Button size="lg" className="mt-auto w-full" onClick={() => setOpenId(row.id)}>
                  {t.open}
                </Button>
              </Card>
            </li>
          ))}
        </ul>
      )}

      <Dialog open={editing} onClose={() => setEditing(false)} title={t.program} closeLabel={messages.trading.close}>
        {rules && (
          <ProgramForm
            program={rules}
            messages={messages}
            onSaved={() => {
              setEditing(false);
              program.reload();
            }}
          />
        )}
      </Dialog>
      <Dialog open={openId !== null} onClose={() => setOpenId(null)} title={opened?.first_name ?? t.title} closeLabel={messages.trading.close}>
        {openId && <DetailPanel key={openId} id={openId} locale={locale} messages={messages} onChanged={onChanged} />}
      </Dialog>
    </>
  );
}
