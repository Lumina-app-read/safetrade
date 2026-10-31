"use client";

import { ArrowDownRight, ArrowUpRight, Layers, LoaderCircle, Shield, ShieldCheck, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { SignedAmount } from "@/components/ui/amount";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import type { Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";

import { codeText, priceDecimals } from "./labels";
import type { Asset, Position } from "./types";
import { useNow } from "./use-live";

const POINTS = 120;

function elapsed(from: string | null, now: number): string {
  const seconds = from && now ? Math.max(0, Math.floor((now - new Date(from).getTime()) / 1000)) : 0;
  const m = Math.floor(seconds / 60);
  const s = String(seconds % 60).padStart(2, "0");
  return m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}` : `${m}:${s}`;
}

/** Évolution du résultat depuis l'ouverture de la page : valeurs reçues du backend uniquement. */
function Sparkline({ values, label }: { values: number[]; label: string }) {
  if (values.length < 2) return null;
  const low = Math.min(...values, 0);
  const high = Math.max(...values, 0);
  const range = high - low || 1;
  const y = (value: number) => 38 - ((value - low) / range) * 36;
  const path = values.map((value, index) => `${(index / (values.length - 1)) * 100},${y(value).toFixed(1)}`).join(" ");
  const up = (values.at(-1) ?? 0) >= 0;
  return (
    <svg viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label={label} className={cn("h-10 w-24 shrink-0", up ? "text-gain" : "text-loss")}>
      <line x1="0" x2="100" y1={y(0)} y2={y(0)} className="stroke-line" strokeWidth="1" vectorEffect="non-scaling-stroke" />
      <polyline points={path} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <dt className="text-small text-muted">{label}</dt>
      <dd className="font-medium tabular-nums">{children}</dd>
    </div>
  );
}

function PositionCard({
  position,
  history,
  asset,
  now,
  locale,
  messages,
  onChanged,
}: {
  position: Position;
  history: number[];
  asset: Asset | undefined;
  now: number;
  locale: Locale;
  messages: Messages;
  onChanged: () => void;
}) {
  const t = messages.trading.positions;
  const f = formatters(locale);
  const [closing, setClosing] = useState(false);
  const [failure, setFailure] = useState<{ code: string } | null>(null);
  // Valeur pas encore fournie par Deriv, juste après l'ouverture.
  const money = (value: string | null) => (value === null ? t.awaiting : f.money(Number(value)));
  const profit = Number(position.current_profit ?? 0);
  const protection = position.protection;
  const decimals = asset ? priceDecimals(asset.pip_size) : 2;
  const Direction = position.direction === "up" ? ArrowUpRight : ArrowDownRight;

  async function close() {
    setClosing(true);
    setFailure(null);
    const result = await api(`/trading/positions/${position.id}/close`, { method: "POST" });
    if (!result.ok) {
      setClosing(false);
      setFailure(result);
    }
    onChanged();
  }

  if (position.status !== "open") {
    return (
      <li className="flex items-center gap-3 rounded-lg border border-line p-4">
        <LoaderCircle size={20} strokeWidth={1.5} aria-hidden className="shrink-0 animate-spin text-muted" />
        <div>
          <p className="font-medium">{asset?.name ?? position.symbol}</p>
          <p className="text-small text-muted">{position.status === "unknown" ? t.unknown : t.opening}</p>
        </div>
      </li>
    );
  }

  return (
    <li className="flex flex-col gap-4 rounded-lg border border-line p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-page text-fg">
            <Direction size={20} strokeWidth={1.5} aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="truncate font-medium">{asset?.name ?? position.symbol}</p>
            <p className="text-small text-muted">
              {position.direction === "up" ? t.up : t.down} · x{position.multiplier} · {elapsed(position.opened_at, now)}
            </p>
          </div>
        </div>
        <Badge tone={position.close_requested ? "warn" : "neutral"}>{position.close_requested ? t.closing : t.open}</Badge>
      </div>

      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-small text-muted">{t.net}</p>
          <p className="text-kpi font-medium">
            {position.current_profit === null ? t.awaiting : <SignedAmount value={profit} formatted={f.money(profit)} />}
          </p>
        </div>
        <Sparkline values={history} label={t.evolution} />
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
        <Fact label={t.stake}>{money(position.buy_price ?? position.stake)}</Fact>
        <Fact label={t.commission}>{money(position.commission)}</Fact>
        <Fact label={t.peak}>{money(position.peak_profit)}</Fact>
        <Fact label={t.entry}>{position.entry_spot ? f.price(Number(position.entry_spot), decimals) : t.awaiting}</Fact>
      </dl>

      <div className="rounded-lg bg-page p-3">
        <p className="mb-2 flex items-center gap-1.5 text-small font-medium text-muted">
          {protection?.ratchet_active ? <ShieldCheck size={16} strokeWidth={1.5} aria-hidden className="text-gain" /> : <Shield size={16} strokeWidth={1.5} aria-hidden />}
          {t.protections}
        </p>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
          <Fact label={protection?.floor_active ? t.floorActive : t.stopAtDeriv}>-{money(position.current_stop ?? position.stop_loss)}</Fact>
          <Fact label={t.worstCase}>{protection ? `-${money(protection.worst_case_loss)}` : t.awaiting}</Fact>
          <Fact label={protection?.ratchet_active ? t.locked : t.activation}>
            {protection?.ratchet_active ? money(protection.locked_level) : money(protection?.activation_level ?? null)}
          </Fact>
          <Fact label={t.stopSpot}>{position.stop_spot ? f.price(Number(position.stop_spot), decimals) : t.awaiting}</Fact>
        </dl>
        {protection?.ratchet_active && <p className="mt-2 text-small text-muted">{t.lockedNote}</p>}
      </div>

      {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
      <Button size="lg" className="w-full" onClick={close} pending={closing || position.close_requested} disabled={position.close_requested}>
        {!(closing || position.close_requested) && <X size={18} strokeWidth={1.5} aria-hidden />}
        {closing || position.close_requested ? t.closing : t.close}
      </Button>
    </li>
  );
}

/** Positions en cours, relues toutes les 2 secondes depuis le backend. */
export function PositionsPanel({
  positions,
  assets,
  loading,
  locale,
  messages,
  onChanged,
}: {
  positions: Position[];
  assets: Asset[];
  loading: boolean;
  locale: Locale;
  messages: Messages;
  onChanged: () => void;
}) {
  const t = messages.trading.positions;
  const now = useNow();
  const memory = useRef(new Map<string, number[]>());
  const [histories, setHistories] = useState<Record<string, number[]>>({});
  const signature = useMemo(() => positions.map((p) => `${p.id}:${p.current_profit}`).join("|"), [positions]);

  useEffect(() => {
    const next: Record<string, number[]> = {};
    for (const position of positions) {
      if (position.current_profit === null) continue;
      const values = [...(memory.current.get(position.id) ?? []), Number(position.current_profit)].slice(-POINTS);
      memory.current.set(position.id, values);
      next[position.id] = values;
    }
    const timer = setTimeout(() => setHistories(next), 0);
    return () => clearTimeout(timer);
    // La signature change exactement quand un résultat change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  if (loading) return <p className="py-8 text-center text-muted">{messages.trading.loading}</p>;
  if (positions.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-10 text-center">
        <span className="grid size-11 place-items-center rounded-xl bg-page text-muted">
          <Layers size={20} strokeWidth={1.5} aria-hidden />
        </span>
        <p className="font-medium">{t.emptyTitle}</p>
        <p className="max-w-sm text-small text-muted">{t.emptyBody}</p>
      </div>
    );
  }
  return (
    <ul className={cn("grid gap-3", positions.length > 1 && "xl:grid-cols-2")}>
      {positions.map((position) => (
        <PositionCard
          key={position.id}
          position={position}
          history={histories[position.id] ?? []}
          asset={assets.find((a) => a.symbol === position.symbol)}
          now={now}
          locale={locale}
          messages={messages}
          onChanged={onChanged}
        />
      ))}
    </ul>
  );
}

export function closeReason(messages: Messages, reason: string | null): string {
  const t = messages.trading.closeReasons;
  const key = (reason ?? "deriv") as keyof typeof t;
  return t[key] ?? codeText(messages, reason);
}
