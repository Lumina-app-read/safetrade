"use client";

import { ArrowDownRight, ArrowUpRight, CircleAlert, FlaskConical, History, Layers, LoaderCircle, Lock, ScrollText, SlidersHorizontal, WifiOff, type LucideIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { FitAmount, FitValue } from "@/components/ui/fit-value";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { cn } from "@/lib/cn";

import { BotPanel } from "./bot-panel";
import { DerivPanel } from "./deriv-panel";
import { HistoryPanel } from "./history-panel";
import { JournalPanel } from "./journal-panel";
import { priceDecimals } from "./labels";
import { PositionsPanel } from "./positions-panel";
import { PriceChart } from "./price-chart";
import { RiskPanel } from "./risk-panel";
import { SettingsForm } from "./settings-form";
import type { Asset, AssetStatus, BotResponse, DerivConnection, SettingsResponse, Summary } from "./types";
import { useMarket, useNow, usePolled, type Market } from "./use-live";

const GRANULARITIES = [60, 300, 900, 3600] as const;
const STATUS_TONES: Record<AssetStatus, BadgeTone> = {
  live: "gain",
  closed: "neutral",
  suspended: "warn",
  stale: "warn",
  unavailable: "warn",
};
// Marché ouvert sans nouveau prix depuis cette durée : l'écran le dit.
const FROZEN_SECONDS = 15;

type Tab = "positions" | "history" | "journal";

function Notice({ icon: Icon, tone, children }: { icon: LucideIcon; tone: "warn" | "error" | "info"; children: ReactNode }) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn(
        "flex animate-fade items-start gap-2.5 rounded-lg border p-3",
        tone === "error" ? "border-loss/40 bg-loss-soft" : tone === "warn" ? "border-warn-line/40 bg-warn-soft" : "border-line bg-card",
      )}
    >
      <Icon size={18} strokeWidth={1.5} aria-hidden className={cn("mt-px shrink-0", tone === "error" ? "text-loss" : tone === "warn" ? "text-warn" : "text-muted")} />
      <p>{children}</p>
    </div>
  );
}

function InstrumentStrip({
  market,
  selected,
  onSelect,
  locale,
  messages,
}: {
  market: Market;
  selected: string | null;
  onSelect: (symbol: string) => void;
  locale: Locale;
  messages: Messages;
}) {
  const t = messages.trading;
  const f = formatters(locale);
  if (market.loading) {
    return (
      <div aria-hidden className="flex gap-2 overflow-hidden">
        {[0, 1, 2, 3].map((n) => (
          <div key={n} className="h-16 w-36 shrink-0 animate-pulse-dot rounded-lg bg-page" />
        ))}
      </div>
    );
  }
  return (
    <div role="listbox" aria-label={t.instruments} className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:thin]">
      {market.assets.map((asset) => {
        const tick = market.prices[asset.symbol] ?? asset.tick;
        const active = asset.symbol === selected;
        return (
          <button
            key={asset.symbol}
            type="button"
            role="option"
            aria-selected={active}
            onClick={() => onSelect(asset.symbol)}
            className={cn(
              "flex min-h-16 w-40 shrink-0 flex-col justify-center gap-0.5 rounded-lg border px-3 py-2 text-left transition-colors",
              active ? "border-accent bg-card" : "border-line bg-page hover:border-muted/60",
            )}
          >
            <span className="flex items-center gap-1.5">
              <span
                aria-hidden
                className={cn("size-1.5 shrink-0 rounded-full", asset.status === "live" ? "animate-pulse-dot bg-gain" : asset.status === "closed" ? "bg-muted" : "bg-warn-line")}
              />
              <span className="truncate text-small font-medium">{asset.name}</span>
            </span>
            <span className="tabular-nums">{tick ? f.price(tick.quote, priceDecimals(asset.pip_size)) : t.statuses[asset.status]}</span>
          </button>
        );
      })}
    </div>
  );
}

function Quote({ asset, price, locale, messages }: { asset: Asset; price: number | null; locale: Locale; messages: Messages }) {
  const f = formatters(locale);
  const decimals = priceDecimals(asset.pip_size);
  const previous = useRef<number | null>(null);
  const [trend, setTrend] = useState<"up" | "down" | null>(null);
  useEffect(() => {
    if (price === null) return;
    const before = previous.current;
    previous.current = price;
    if (before === null || before === price) return;
    const timer = setTimeout(() => setTrend(price > before ? "up" : "down"), 0);
    return () => clearTimeout(timer);
  }, [price]);
  const Icon = trend === "down" ? ArrowDownRight : ArrowUpRight;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <h2 className="text-h3 font-medium">{asset.name}</h2>
      <Badge tone={STATUS_TONES[asset.status]}>{messages.trading.statuses[asset.status]}</Badge>
      {price !== null && (
        <span className="inline-flex items-center gap-1 text-h3 font-medium tabular-nums">
          {trend && <Icon size={18} strokeWidth={1.5} aria-hidden className={trend === "up" ? "text-gain" : "text-loss"} />}
          {f.price(price, decimals)}
        </span>
      )}
    </div>
  );
}

function Kpi({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-xl border border-line bg-card p-4 shadow-card">
      <span className="text-small text-muted">{label}</span>
      {children}
      {hint && <span className="text-small text-muted">{hint}</span>}
    </div>
  );
}

/**
 * Tableau de trading. Téléphone : marché, pilotage, puis positions, dans l'ordre d'usage.
 * Ordinateur : graphique à gauche, pilotage et risque à droite. Toutes les données viennent
 * de l'API ; seul le moteur (`safetradev2-engine`) passe des ordres.
 */
export function TradingPage({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.trading;
  const f = formatters(locale);
  const market = useMarket();
  const bot = usePolled<BotResponse>("/trading/bot", 2000);
  const deriv = usePolled<DerivConnection>("/deriv/connection", 30000);
  const settings = usePolled<SettingsResponse>("/trading/settings", 0);
  const summary = usePolled<Summary>("/trading/summary", 4000);
  const now = useNow(5000);

  const [picked, setPicked] = useState<string | null>(null);
  const [granularity, setGranularity] = useState<number>(GRANULARITIES[0]);
  const [tab, setTab] = useState<Tab>("positions");
  const [settingsOpen, setSettingsOpen] = useState(false);

  const session = bot.data?.session ?? null;
  const positions = useMemo(() => bot.data?.open_positions ?? [], [bot.data]);
  const symbol = picked ?? session?.symbol ?? market.assets.find((a) => a.status === "live")?.symbol ?? market.assets[0]?.symbol ?? null;
  const asset = market.assets.find((a) => a.symbol === symbol);
  const tick = symbol ? (market.prices[symbol] ?? asset?.tick ?? null) : null;

  const connection = deriv.data;
  const derivReady = connection?.connected === true && connection.token_valid && connection.selected.account_id !== null;
  const kind = session?.account_kind ?? (connection?.connected ? connection.selected.kind : null);
  const balance = connection?.connected ? connection.accounts.find((a) => a.account_id === connection.selected.account_id) : undefined;
  const allowed = (settings.data?.settings.allowed_symbols as string[] | undefined) ?? [];

  const blocked = !derivReady
    ? t.bot.blockedDeriv
    : !asset
      ? t.bot.blockedAsset
      : asset.status !== "live"
        ? interpolate(t.bot.blockedMarket, { name: asset.name, status: t.statuses[asset.status] })
        : settings.data && !allowed.includes(asset.symbol)
          ? t.bot.blockedAllowed
          : null;

  const frozen = asset?.status === "stale" || (asset?.status === "live" && tick !== null && now > 0 && now / 1000 - tick.received_at > FROZEN_SECONDS);
  const reload = () => {
    bot.reload();
    summary.reload();
  };

  const tabs: Array<{ id: Tab; label: string; icon: LucideIcon; count?: number }> = [
    { id: "positions", label: t.tabs.positions, icon: Layers, count: positions.length },
    { id: "history", label: t.tabs.history, icon: History },
    { id: "journal", label: t.tabs.journal, icon: ScrollText },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1.5">
          <h1 className="text-h1">{messages.nav.trading}</h1>
          <div className="flex flex-wrap items-center gap-1.5">
            {kind === "demo" && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1 text-small font-medium text-accent-text">
                <FlaskConical size={14} strokeWidth={1.5} aria-hidden />
                {t.env.demo}
              </span>
            )}
            <span className="inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1 text-small text-muted">
              <Lock size={14} strokeWidth={1.5} aria-hidden />
              {t.env.realLocked}
            </span>
          </div>
        </div>
        <Button size="lg" onClick={() => setSettingsOpen(true)} disabled={!settings.data} aria-label={t.settings.title} className="shrink-0 max-sm:w-12 max-sm:px-0">
          <SlidersHorizontal size={18} strokeWidth={1.5} aria-hidden />
          <span className="max-sm:hidden">{t.settings.title}</span>
        </Button>
      </div>

      <div className="flex flex-col gap-2" aria-live="polite">
        {(bot.error || market.error) && (
          <Notice icon={WifiOff} tone="error">
            {t.notices.server}
          </Notice>
        )}
        {market.stream === "lost" && (
          <Notice icon={LoaderCircle} tone="warn">
            {t.notices.stream}
          </Notice>
        )}
        {frozen && market.stream !== "lost" && (
          <Notice icon={CircleAlert} tone="warn">
            {t.notices.frozen}
          </Notice>
        )}
        {session && !session.engine_online && session.state !== "starting" && (
          <Notice icon={CircleAlert} tone="error">
            {t.notices.engine}
          </Notice>
        )}
        {session?.state === "starting" && (
          <Notice icon={LoaderCircle} tone="info">
            {t.notices.starting}
          </Notice>
        )}
        {session?.engine_online && !session.deriv_connected && session.state !== "starting" && (
          <Notice icon={WifiOff} tone="warn">
            {t.notices.deriv}
          </Notice>
        )}
        {asset?.status === "closed" && (
          <Notice icon={CircleAlert} tone="info">
            {interpolate(t.notices.closed, { name: asset.name })}
          </Notice>
        )}
      </div>

      {/* Téléphone : marché, bot, indicateurs, positions, risque, compte. */}
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <section aria-label={t.kpi.title} className="grid min-w-0 grid-cols-2 gap-3 max-lg:order-4 lg:col-span-2 lg:grid-cols-4">
        <Kpi label={t.kpi.balance} hint={kind === "demo" ? t.kpi.demoFunds : undefined}>
          <FitValue
            size={balance ? "h3" : "text"}
            text={balance ? f.moneyShort(Number(balance.balance), balance.currency) : deriv.loading ? t.loading : deriv.error && !deriv.data ? t.kpi.unavailable : t.kpi.notConnected}
            title={balance ? f.money(Number(balance.balance), balance.currency) : undefined}
          />
        </Kpi>
        <Kpi label={t.kpi.session}>
          {session ? (
            <FitAmount size="h3" value={Number(session.session_net)} formatted={f.moneyShort(Number(session.session_net))} title={f.money(Number(session.session_net))} />
          ) : (
            <FitValue size="text" text={t.kpi.noSession} />
          )}
        </Kpi>
        <Kpi label={t.kpi.day}>
          {summary.data ? (
            <FitAmount size="h3" value={Number(summary.data.day_net)} formatted={f.moneyShort(Number(summary.data.day_net))} title={f.money(Number(summary.data.day_net))} />
          ) : (
            <FitValue size="text" text={t.loading} />
          )}
        </Kpi>
        <Kpi label={t.kpi.winRate} hint={summary.data?.trades ? interpolate(t.kpi.sample, { count: summary.data.trades }) : t.kpi.noTrades}>
          <FitValue size={summary.data?.win_rate != null ? "h3" : "text"} text={summary.data?.win_rate != null ? f.percent(summary.data.win_rate) : summary.data ? t.kpi.noPosition : t.loading} />
        </Kpi>
      </section>

        <Card className="flex min-w-0 flex-col gap-3 p-3 max-lg:order-2 sm:p-4 lg:col-start-1 lg:row-start-2">
          <InstrumentStrip market={market} selected={symbol} onSelect={setPicked} locale={locale} messages={messages} />
          <div className="flex flex-wrap items-center justify-between gap-2 px-1">
            {asset ? <Quote key={asset.symbol} asset={asset} price={tick?.quote ?? null} locale={locale} messages={messages} /> : <span />}
            <div role="radiogroup" aria-label={t.chart.interval} className="flex rounded-lg border border-line p-0.5">
              {GRANULARITIES.map((value) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={granularity === value}
                  onClick={() => setGranularity(value)}
                  className="min-h-9 min-w-11 rounded-md px-2 text-label font-medium text-muted transition-colors aria-checked:bg-primary aria-checked:text-on-primary"
                >
                  {t.chart.intervals[String(value) as keyof typeof t.chart.intervals]}
                </button>
              ))}
            </div>
          </div>
          {symbol && asset ? (
            <PriceChart
              key={`${symbol}-${granularity}`}
              symbol={symbol}
              granularity={granularity}
              decimals={priceDecimals(asset.pip_size)}
              market={market}
              positions={positions}
              locale={locale}
              messages={messages}
            />
          ) : (
            <div className="grid h-64 place-items-center text-muted">{market.loading ? t.loading : t.chart.noAssets}</div>
          )}
        </Card>

        <aside className="flex min-w-0 flex-col gap-4 max-lg:contents lg:col-start-2 lg:row-span-2 lg:row-start-2">
          <div className="min-w-0 max-lg:order-3">
            <BotPanel bot={bot.data} asset={asset} canTrade={!blocked} blocked={blocked} onChanged={reload} messages={messages} />
          </div>
          <div className="min-w-0 max-lg:order-6">
            <RiskPanel risk={bot.data?.risk ?? null} locale={locale} messages={messages} />
          </div>
          {/* Sans compte connecté, la connexion passe en tête : rien d'autre n'est possible. */}
          <div className={cn("min-w-0", derivReady || deriv.loading ? "max-lg:order-7" : "max-lg:order-1")}>
            <DerivPanel
              connection={connection}
              loading={deriv.loading}
              botActive={session !== null}
              locale={locale}
              messages={messages}
              onChanged={deriv.reload}
            />
          </div>
        </aside>

        <Card className="flex min-w-0 flex-col gap-4 p-4 max-lg:order-5 sm:p-5 lg:col-start-1 lg:row-start-3">
          <div role="tablist" aria-label={t.tabs.label} className="flex gap-1 border-b border-line">
            {tabs.map(({ id, label, icon: Icon, count }) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={tab === id}
                onClick={() => setTab(id)}
                className="-mb-px flex min-h-11 flex-1 items-center justify-center gap-1.5 border-b-2 border-transparent px-2 text-label font-medium text-muted transition-colors aria-selected:border-accent aria-selected:text-fg sm:flex-none sm:px-3"
              >
                <Icon size={16} strokeWidth={1.5} aria-hidden className="max-[400px]:hidden" />
                {label}
                {count ? <span className="rounded-full bg-page px-1.5 text-small tabular-nums">{count}</span> : null}
              </button>
            ))}
          </div>
          <div role="tabpanel">
            {tab === "positions" && (
              <PositionsPanel positions={positions} assets={market.assets} loading={bot.loading} locale={locale} messages={messages} onChanged={reload} />
            )}
            {tab === "history" && <HistoryPanel assets={market.assets} locale={locale} messages={messages} />}
            {tab === "journal" && <JournalPanel locale={locale} messages={messages} />}
          </div>
        </Card>
      </div>

      <p className="text-small text-muted">{t.disclaimer}</p>

      <Dialog open={settingsOpen} onClose={() => setSettingsOpen(false)} title={t.settings.title} closeLabel={t.close}>
        {settings.data && (
          <SettingsForm data={settings.data} assets={market.assets} locale={locale} messages={messages} onSaved={settings.reload} />
        )}
      </Dialog>
    </div>
  );
}
