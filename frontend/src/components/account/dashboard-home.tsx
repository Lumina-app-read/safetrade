"use client";

import {
  ArrowRight,
  Bot,
  ChartLine,
  Check,
  CreditCard,
  Link2,
  MailCheck,
  ShieldCheck,
  SlidersHorizontal,
  TriangleAlert,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { useSession } from "@/components/shell/session";
import { SignedAmount } from "@/components/ui/amount";
import { Badge } from "@/components/ui/badge";
import { Card, SectionTitle } from "@/components/ui/card";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { cn } from "@/lib/cn";

import type { BotResponse, DerivConnection, Summary } from "../trading/types";
import { usePolled } from "../trading/use-live";

function Stat({ label, icon: Icon, children, hint }: { label: string; icon: LucideIcon; children: ReactNode; hint: string }) {
  return (
    <Card className="flex min-w-0 flex-col gap-2 p-4 sm:p-6">
      <div className="flex items-center justify-between gap-2 text-muted">
        <span className="truncate text-label font-medium">{label}</span>
        <Icon size={20} strokeWidth={1.5} aria-hidden className="shrink-0 max-sm:hidden" />
      </div>
      <div className="text-kpi font-medium">{children}</div>
      <p className="text-small text-muted">{hint}</p>
    </Card>
  );
}

/**
 * Tableau de bord client : uniquement des données réelles. Tant que Deriv n'est pas
 * connecté, les valeurs sont des états vides, jamais des chiffres inventés.
 */
export function DashboardHome({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.dashboard;
  const { user } = useSession();
  const f = formatters(locale);
  const deriv = usePolled<DerivConnection>("/deriv/connection", 60000);
  const bot = usePolled<BotResponse>("/trading/bot", 5000);
  const summary = usePolled<Summary>("/trading/summary", 15000);
  const connection = deriv.data?.connected && deriv.data.token_valid ? deriv.data : null;
  const account = connection?.accounts.find((a) => a.account_id === connection.selected.account_id);
  const session = bot.data?.session ?? null;
  const trading = `/${locale}/trading`;

  const steps: Array<{ label: string; done: boolean; icon: LucideIcon; href?: string }> = [
    { label: t.stepEmail, done: true, icon: MailCheck },
    {
      label: t.stepMfa,
      done: user.mfa_enabled,
      icon: ShieldCheck,
      href: `/${locale}/account/security`,
    },
    { label: t.stepDeriv, done: connection !== null, icon: Link2, href: trading },
    { label: t.stepLimits, done: session !== null || (summary.data?.trades ?? 0) > 0, icon: SlidersHorizontal, href: trading },
  ];
  const done = steps.filter((s) => s.done).length;

  return (
    <>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          {/* Seul emoji autorisé de l'interface (section 15). */}
          <h1 className="text-h1">
            {interpolate(t.greeting, { name: user.first_name })} <span aria-hidden>👋</span>
          </h1>
          <p className="mt-1 text-muted">{t.subtitle}</p>
        </div>
        <Link
          href={`/${locale}/trading`}
          className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-primary px-5 text-label font-medium text-on-primary transition-opacity hover:opacity-90"
        >
          <ChartLine size={18} strokeWidth={1.5} aria-hidden />
          {t.openTrading}
        </Link>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1.1fr_1fr]">
        <section className="relative flex min-h-52 flex-col justify-between gap-6 overflow-hidden rounded-xl bg-anthracite p-6 text-on-anthracite sm:p-8">
          <span
            aria-hidden
            className="pointer-events-none absolute -top-24 -right-20 size-72 rounded-full border-[36px] border-brand-ring"
          />
          <span
            aria-hidden
            className="pointer-events-none absolute -right-4 -bottom-28 size-44 rounded-full border-[28px] border-brand-ring/60"
          />
          <span className="relative w-fit rounded-full border border-on-anthracite/25 px-3 py-1 text-small font-medium">
            {t.bannerMode}
          </span>
          <div className="relative">
            <h2 className="text-h2">{connection ? t.bannerConnected : t.bannerTitle}</h2>
            <p className="mt-2 max-w-md text-on-anthracite/75">{connection ? t.bannerConnectedBody : t.bannerBody}</p>
          </div>
        </section>

        <div className="grid grid-cols-2 gap-3 sm:gap-4">
          <Stat label={t.balance} icon={Wallet} hint={account ? t.balanceDemo : t.balanceEmpty}>
            {account ? f.money(Number(account.balance), account.currency) : "—"}
          </Stat>
          <Stat label={t.today} icon={ChartLine} hint={summary.data?.trades ? t.todayReal : t.todayEmpty}>
            {summary.data?.trades ? <SignedAmount value={Number(summary.data.day_net)} formatted={f.money(Number(summary.data.day_net))} /> : "—"}
          </Stat>
          <Stat label={t.bot} icon={Bot} hint={session ? session.symbol : t.botEmpty}>
            <Badge tone="neutral">{messages.trading.bot.states[session?.state ?? "stopped"]}</Badge>
          </Stat>
          <Stat label={t.access} icon={CreditCard} hint={t.accessEmpty}>
            —
          </Stat>
        </div>
      </div>

      <SectionTitle className="flex items-center justify-between">
        {t.stepsTitle}
        <span className="tracking-normal normal-case">{interpolate(t.stepsProgress, { done, total: steps.length })}</span>
      </SectionTitle>
      <Card className="p-2 sm:p-3">
        <div aria-hidden className="mx-2 mt-2 mb-1 h-1 overflow-hidden rounded-full bg-page">
          <div className="h-full rounded-full bg-gain transition-[width] duration-500" style={{ width: `${(done / steps.length) * 100}%` }} />
        </div>
        <ul>
          {steps.map(({ label, done: isDone, icon: Icon, href }) => {
            const row = (
              <>
                <span
                  className={cn(
                    "grid size-9 shrink-0 place-items-center rounded-lg",
                    isDone ? "bg-gain-soft text-gain" : "bg-page text-muted",
                  )}
                >
                  {isDone ? <Check size={18} strokeWidth={1.75} aria-hidden /> : <Icon size={18} strokeWidth={1.5} aria-hidden />}
                </span>
                <span className={cn("min-w-0 flex-1", !isDone && !href && "text-muted")}>{label}</span>
              </>
            );
            const rowClass = "flex min-h-14 items-center gap-3 rounded-lg px-2";
            if (isDone || !href) {
              return (
                <li key={label} className={rowClass}>
                  {row}
                  {!isDone && <span className="text-small text-muted">{t.stepSoon}</span>}
                </li>
              );
            }
            return (
              <li key={label}>
                <Link href={href} className={cn(rowClass, "transition-colors hover:bg-page")}>
                  {row}
                  <span className="inline-flex items-center gap-1 text-label font-medium text-accent-text">
                    {t.stepAction}
                    <ArrowRight size={16} strokeWidth={1.5} aria-hidden />
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </Card>

      <p className="mt-6 flex items-start gap-2 text-small text-muted">
        <TriangleAlert size={16} strokeWidth={1.5} aria-hidden className="mt-px shrink-0 text-warn" />
        {t.risk}
      </p>
    </>
  );
}
