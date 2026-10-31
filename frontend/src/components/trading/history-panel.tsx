"use client";

import { ArrowDownRight, ArrowUpRight, History } from "lucide-react";
import type { ReactNode } from "react";

import { SignedAmount } from "@/components/ui/amount";
import { Alert } from "@/components/ui/alert";
import { Table, Td, Th } from "@/components/ui/table";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import type { Messages } from "@/i18n/messages";
import { errorMessage } from "@/lib/api";

import { closeReason } from "./positions-panel";
import type { Asset, Position, Summary } from "./types";
import { usePolled } from "./use-live";

const REFRESH_MS = 10000;

/** Courbe des résultats nets cumulés, à partir des positions réellement clôturées. */
function ResultCurve({ summary, label }: { summary: Summary; label: string }) {
  const values = summary.curve.map((point) => Number(point.net));
  if (values.length < 2) return null;
  const low = Math.min(...values, 0);
  const high = Math.max(...values, 0);
  const range = high - low || 1;
  const y = (value: number) => 78 - ((value - low) / range) * 76;
  const points = values.map((value, index) => `${(index / (values.length - 1)) * 300},${y(value).toFixed(1)}`).join(" ");
  const up = (values.at(-1) ?? 0) >= 0;
  return (
    <svg viewBox="0 0 300 80" preserveAspectRatio="none" role="img" aria-label={label} className={up ? "h-20 w-full text-gain" : "h-20 w-full text-loss"}>
      <line x1="0" x2="300" y1={y(0)} y2={y(0)} className="stroke-line" strokeWidth="1" strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function Statistic({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <span className="text-small text-muted">{label}</span>
      <span className="font-medium tabular-nums">{children}</span>
    </div>
  );
}

function PerformanceBlock({ summary, locale, messages }: { summary: Summary; locale: Locale; messages: Messages }) {
  const t = messages.trading.history;
  const f = formatters(locale);
  const money = (value: string | null) => (value === null ? "—" : f.money(Number(value)));
  return (
    <div className="flex flex-col gap-3 rounded-lg bg-page p-4">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Statistic label={t.total}>
          <SignedAmount value={Number(summary.total_net)} formatted={f.money(Number(summary.total_net))} />
        </Statistic>
        <Statistic label={t.trades}>{`${summary.trades} (${summary.wins} / ${summary.losses})`}</Statistic>
        <Statistic label={t.averageGain}>{money(summary.average_gain)}</Statistic>
        <Statistic label={t.averageLoss}>{money(summary.average_loss)}</Statistic>
      </dl>
      <ResultCurve summary={summary} label={t.curve} />
      <p className="text-small text-muted">{t.sampleNote}</p>
    </div>
  );
}

/** Historique lu en base : positions clôturées et résultats de référence de Deriv. */
export function HistoryPanel({ assets, locale, messages }: { assets: Asset[]; locale: Locale; messages: Messages }) {
  const t = messages.trading.history;
  const f = formatters(locale);
  const list = usePolled<{ positions: Position[] }>("/trading/positions?closed=true&limit=100", REFRESH_MS);
  const stats = usePolled<Summary>("/trading/summary", REFRESH_MS);
  const rows = list.data?.positions ?? [];
  const name = (symbol: string) => assets.find((a) => a.symbol === symbol)?.name ?? symbol;

  if (list.loading) return <p className="py-8 text-center text-muted">{messages.trading.loading}</p>;
  if (list.error && !list.data) return <Alert tone="error">{errorMessage(messages, list.error)}</Alert>;
  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-10 text-center">
        <span className="grid size-11 place-items-center rounded-xl bg-page text-muted">
          <History size={20} strokeWidth={1.5} aria-hidden />
        </span>
        <p className="font-medium">{t.emptyTitle}</p>
        <p className="max-w-sm text-small text-muted">{t.emptyBody}</p>
      </div>
    );
  }

  const stamp = (value: string | null) => (value ? `${f.date(value)} ${f.time(value)}` : "—");
  const direction = (row: Position) => {
    const Icon = row.direction === "up" ? ArrowUpRight : ArrowDownRight;
    return (
      <span className="inline-flex items-center gap-1">
        <Icon size={16} strokeWidth={1.5} aria-hidden />
        {row.direction === "up" ? messages.trading.positions.up : messages.trading.positions.down}
      </span>
    );
  };
  const result = (row: Position) => <SignedAmount value={Number(row.net_result)} formatted={f.money(Number(row.net_result))} />;

  return (
    <div className="flex flex-col gap-4">
      {stats.data && <PerformanceBlock summary={stats.data} locale={locale} messages={messages} />}

      {/* Téléphone : cartes ; le tableau n'apparaît qu'avec assez de largeur. */}
      <ul className="flex flex-col gap-2 md:hidden">
        {rows.map((row) => (
          <li key={row.id} className="flex flex-col gap-1.5 rounded-lg border border-line p-3">
            <div className="flex items-center justify-between gap-3">
              <span className="truncate font-medium">{name(row.symbol)}</span>
              <span className="font-medium">{result(row)}</span>
            </div>
            <div className="flex items-center justify-between gap-3 text-small text-muted">
              <span>{direction(row)}</span>
              <span>{closeReason(messages, row.close_reason)}</span>
            </div>
            <span className="text-small text-muted">{stamp(row.closed_at)}</span>
          </li>
        ))}
      </ul>

      <div className="hidden md:block">
        <Table>
          <thead>
            <tr>
              <Th>{t.closedAt}</Th>
              <Th>{t.asset}</Th>
              <Th>{t.direction}</Th>
              <Th numeric>{t.stake}</Th>
              <Th numeric>{t.net}</Th>
              <Th>{t.exit}</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <Td>{stamp(row.closed_at)}</Td>
                <Td>{name(row.symbol)}</Td>
                <Td>{direction(row)}</Td>
                <Td numeric>{f.money(Number(row.buy_price ?? row.stake))}</Td>
                <Td numeric>{result(row)}</Td>
                <Td>{closeReason(messages, row.close_reason)}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
    </div>
  );
}
