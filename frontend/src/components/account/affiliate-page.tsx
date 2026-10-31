"use client";

import { BadgeCheck, Check, Copy, Gift, Hourglass, Landmark, MessageSquareText, ReceiptText, Share2, TriangleAlert, UserPlus, Users, type LucideIcon } from "lucide-react";
import { useRef, useState, type FormEvent, type ReactNode } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, SectionTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import { FitValue } from "@/components/ui/fit-value";
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
type Referral = { id: string; name: string; joined_at: string; converted: boolean };
type Commission = { id: string; plan: string; amount: string; currency: string; status: string; available_at: string; created_at: string };
type Payout = { id: string; amount: string; currency: string; method: string; paid_at: string };
type View = {
  status: "none" | "pending" | "approved" | "refused" | "suspended";
  program: Program;
  code: string | null;
  link: string | null;
  totals: Totals;
  referrals: Referral[];
  commissions: Commission[];
  payouts: Payout[];
};

const COMMISSION_TONES: Record<string, BadgeTone> = {
  held: "neutral",
  available: "gain",
  paid: "gain",
  cancelled: "warn",
};

/** Conditions du programme : elles viennent du backend, l'administration peut les changer. */
function Rules({ program, locale, messages }: { program: Program; locale: Locale; messages: Messages }) {
  const t = messages.affiliate;
  const f = formatters(locale);
  const rate = Number(program.rate_pct);
  const percent = f.percent(rate / 100, Number.isInteger(rate) ? 0 : 2);
  const rows: Array<[LucideIcon, string]> = [
    [Gift, interpolate(program.recurring ? t.ruleRateRecurring : t.ruleRate, { rate: percent })],
    [UserPlus, interpolate(t.ruleWindow, { days: program.attribution_days })],
    [Hourglass, interpolate(t.ruleHold, { days: program.hold_days })],
  ];
  return (
    <ul className="flex flex-col gap-3">
      {rows.map(([Icon, text]) => (
        <li key={text} className="flex items-start gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-page text-muted">
            <Icon size={18} strokeWidth={1.5} aria-hidden />
          </span>
          <span className="self-center">{text}</span>
        </li>
      ))}
    </ul>
  );
}

function ApplyForm({ messages, onDone }: { messages: Messages; onDone: () => void }) {
  const t = messages.affiliate;
  const [accepted, setAccepted] = useState(false);
  const [termsError, setTermsError] = useState(false);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<{ code: string; retryAfter?: number } | null>(null);
  const { field, validate } = useFormErrors({
    message: (value) => (value.trim().length >= 10 ? undefined : t.messageInvalid),
    payout_details: (value) => (value.trim().length >= 6 ? undefined : t.payoutInvalid),
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fieldsOk = validate(event.currentTarget);
    setTermsError(!accepted);
    if (!fieldsOk || !accepted) return;
    const form = new FormData(event.currentTarget);
    setPending(true);
    setFailure(null);
    const result = await api("/affiliate/apply", {
      body: {
        message: String(form.get("message")).trim(),
        payout_details: String(form.get("payout_details")).trim(),
        accept_terms: accepted,
      },
    });
    setPending(false);
    if (result.ok) onDone();
    else setFailure(result);
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
      <Field label={t.message} icon={MessageSquareText} placeholder={t.messagePlaceholder} maxLength={500} {...field("message")} />
      <Field
        label={t.payout}
        icon={Landmark}
        placeholder={t.payoutPlaceholder}
        hint={t.payoutHint}
        maxLength={200}
        autoComplete="off"
        {...field("payout_details")}
      />
      <Checkbox
        label={t.terms}
        checked={accepted}
        onChange={(e) => {
          setAccepted(e.target.checked);
          setTermsError(!e.target.checked);
        }}
        error={termsError ? t.termsRequired : undefined}
      />
      <Button type="submit" variant="accent" size="lg" pending={pending} className="w-full sm:w-auto sm:self-start">
        {pending ? t.submitting : t.submit}
      </Button>
    </form>
  );
}

function CopyButton({ value, label, messages }: { value: string; label: string; messages: Messages }) {
  const t = messages.affiliate;
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      return; // Presse-papiers refusé : la valeur reste affichée et sélectionnable.
    }
    setCopied(true);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopied(false), 2000);
  }

  return (
    <button
      type="button"
      onClick={copy}
      aria-label={`${copied ? t.copied : t.copy} : ${label}`}
      className="inline-flex size-11 shrink-0 items-center justify-center gap-2 rounded-lg border border-line bg-card text-label font-medium transition-colors hover:bg-page sm:w-auto sm:px-3"
    >
      {copied ? <Check size={18} strokeWidth={1.5} aria-hidden className="text-gain" /> : <Copy size={18} strokeWidth={1.5} aria-hidden />}
      <span className="max-sm:hidden">{copied ? t.copied : t.copy}</span>
    </button>
  );
}

/** Code et lien sur une seule ligne chacun, quelle que soit la largeur de l'écran. */
function ShareCard({ code, link, messages }: { code: string; link: string; messages: Messages }) {
  const t = messages.affiliate;

  async function share() {
    // Feuille de partage du téléphone ; annulée par le client : rien à signaler.
    await navigator.share({ title: "SafeTrade", text: t.shareText, url: link }).catch(() => undefined);
  }

  return (
    <Card className="flex flex-col gap-4 p-4 sm:p-6">
      <span className="flex items-center gap-2 text-small text-gain">
        <BadgeCheck size={16} strokeWidth={1.5} aria-hidden />
        {t.active}
      </span>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-small text-muted">{t.code}</p>
          <p className="text-h2 tracking-[0.08em] select-all">{code}</p>
        </div>
        <CopyButton value={code} label={t.code} messages={messages} />
      </div>
      <div>
        <p className="mb-1.5 text-small text-muted">{t.link}</p>
        <div className="flex items-center gap-2">
          <p title={link} className="flex h-11 min-w-0 flex-1 items-center rounded-lg bg-page px-3">
            <span className="truncate select-all">{link}</span>
          </p>
          <CopyButton value={link} label={t.link} messages={messages} />
        </div>
      </div>
      {typeof navigator !== "undefined" && "share" in navigator && (
        <Button variant="accent" size="lg" className="w-full sm:hidden" onClick={share}>
          <Share2 size={18} strokeWidth={1.5} aria-hidden />
          {t.share}
        </Button>
      )}
    </Card>
  );
}

function Figure({ label, text, wide, gain }: { label: string; text: string; wide?: boolean; gain?: boolean }) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1 bg-card p-4 sm:p-5", wide && "max-lg:col-span-2")}>
      <span className="text-small text-muted">{label}</span>
      <span className={gain ? "text-gain" : undefined}>
        <FitValue text={text} />
      </span>
    </div>
  );
}

function Empty({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <p className="flex items-center gap-2 text-muted">
      <Icon size={18} strokeWidth={1.5} aria-hidden className="shrink-0" />
      {children}
    </p>
  );
}

const ROW = "flex flex-wrap items-center justify-between gap-2 border-b border-line py-3 last:border-b-0";

function Activity({ view, locale, messages }: { view: View; locale: Locale; messages: Messages }) {
  const t = messages.affiliate;
  const f = formatters(locale);
  const statuses = t.commissionStatuses as Record<string, string>;
  const methods = t.methods as Record<string, string>;
  const { totals } = view;
  const amount = (value: string) => f.moneyShort(Number(value), totals.currency);

  return (
    <>
      <section aria-label={t.summary} className="mt-4 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line shadow-card lg:grid-cols-5">
        <Figure label={t.available} text={amount(totals.available)} wide gain={Number(totals.available) > 0} />
        <Figure label={t.held} text={amount(totals.held)} />
        <Figure label={t.paid} text={amount(totals.paid)} />
        <Figure label={t.referrals} text={f.number(totals.referrals)} />
        <Figure label={t.converted} text={f.number(totals.converted)} />
      </section>

      <SectionTitle>{t.referrals}</SectionTitle>
      <Card className="p-4 sm:p-5">
        {view.referrals.length === 0 ? (
          <Empty icon={Users}>{t.noReferrals}</Empty>
        ) : (
          <ul className="flex flex-col">
            {view.referrals.map((row) => (
              <li key={row.id} className={ROW}>
                <span className="min-w-0">
                  <span className="block font-medium">{row.name}</span>
                  <span className="block text-small text-muted">{f.date(row.joined_at)}</span>
                </span>
                <Badge tone={row.converted ? "gain" : "neutral"}>{row.converted ? t.convertedOne : t.registered}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <SectionTitle>{t.commissions}</SectionTitle>
      <Card className="p-4 sm:p-5">
        {view.commissions.length === 0 ? (
          <Empty icon={ReceiptText}>{t.noCommissions}</Empty>
        ) : (
          <ul className="flex flex-col">
            {view.commissions.map((row) => (
              <li key={row.id} className={ROW}>
                <span className="min-w-0">
                  <span className="block font-medium">{planLabel(messages, row.plan)}</span>
                  <span className="block text-small text-muted">
                    {row.status === "held" ? interpolate(t.availableOn, { date: f.date(row.available_at) }) : f.date(row.created_at)}
                  </span>
                </span>
                <span className="flex items-center gap-3">
                  <span className="font-medium tabular-nums">{f.money(Number(row.amount), row.currency)}</span>
                  <Badge tone={COMMISSION_TONES[row.status] ?? "neutral"}>{statuses[row.status] ?? row.status}</Badge>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <SectionTitle>{t.payouts}</SectionTitle>
      <Card className="p-4 sm:p-5">
        {view.payouts.length === 0 ? (
          <Empty icon={Landmark}>{t.noPayouts}</Empty>
        ) : (
          <ul className="flex flex-col">
            {view.payouts.map((row) => (
              <li key={row.id} className={ROW}>
                <span className="min-w-0">
                  <span className="block font-medium">{methods[row.method] ?? row.method}</span>
                  <span className="block text-small text-muted">{f.date(row.paid_at)}</span>
                </span>
                <span className="font-medium tabular-nums">{f.money(Number(row.amount), row.currency)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}

/** Espace affilié : statut, code et soldes viennent du backend, rien n'est calculé ici. */
export function AffiliatePage({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.affiliate;
  const affiliate = usePolled<View>("/affiliate/me", 30000);
  const view = affiliate.data;

  return (
    <div className="flex flex-col">
      <h1 className="text-h1">{messages.nav.affiliate}</h1>
      <p className="mt-1 max-w-2xl text-muted">{t.intro}</p>
      {affiliate.error && !view && (
        <div className="mt-6">
          <Alert tone="error">{errorMessage(messages, affiliate.error)}</Alert>
        </div>
      )}
      {!view && !affiliate.error && <p className="mt-6 text-muted">{messages.trading.loading}</p>}

      {view && (view.status === "none" || view.status === "refused") && (
        <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <Card className="p-5 sm:p-6">
            <h2 className="mb-4 text-h3 font-medium">{t.rulesTitle}</h2>
            <Rules program={view.program} locale={locale} messages={messages} />
          </Card>
          <Card className="p-5 sm:p-6">
            <h2 className="mb-4 text-h3 font-medium">{t.applyTitle}</h2>
            {view.status === "refused" && (
              <div className="mb-4">
                <Alert tone="info">{t.refusedBody}</Alert>
              </div>
            )}
            <ApplyForm messages={messages} onDone={affiliate.reload} />
          </Card>
        </div>
      )}

      {view?.status === "pending" && (
        <Card className="mt-6 flex items-start gap-4 p-5 sm:p-6">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-page text-muted">
            <Hourglass size={20} strokeWidth={1.5} aria-hidden />
          </span>
          <span>
            <span className="block text-h3 font-medium">{t.pendingTitle}</span>
            <span className="mt-1 block text-muted">{t.pendingBody}</span>
          </span>
        </Card>
      )}

      {view?.status === "suspended" && (
        <>
          <div className="mt-6">
            <Alert tone="error">{t.suspendedBody}</Alert>
          </div>
          <Activity view={view} locale={locale} messages={messages} />
        </>
      )}

      {view?.status === "approved" && view.code && view.link && (
        <>
          <div className="mt-6">
            <ShareCard code={view.code} link={view.link} messages={messages} />
          </div>
          <Activity view={view} locale={locale} messages={messages} />
          <p className="mt-6 flex items-start gap-2 text-small text-muted">
            <TriangleAlert size={16} strokeWidth={1.5} aria-hidden className="mt-px shrink-0 text-warn" />
            {t.reminder}
          </p>
        </>
      )}
    </div>
  );
}
