"use client";

import { LoaderCircle } from "lucide-react";
import type { IChartApi, IPriceLine, ISeriesApi, UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef, useState } from "react";

import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import type { Messages } from "@/i18n/messages";
import { api } from "@/lib/api";

import type { Candle, Position, Tick } from "./types";
import type { Market } from "./use-live";

type Bar = { time: UTCTimestamp; open: number; high: number; low: number; close: number };

const VISIBLE_BARS = 90;
const REFRESH_MS = 60000;

/** Couleurs lues dans les jetons du thème : le graphique suit le clair et le sombre. */
function theme() {
  const style = getComputedStyle(document.documentElement);
  const read = (name: string) => style.getPropertyValue(name).trim();
  return { text: read("--muted"), line: read("--line"), gain: read("--gain"), loss: read("--loss"), fg: read("--fg") };
}

function chartOptions() {
  const c = theme();
  return {
    layout: { textColor: c.text },
    grid: { vertLines: { color: c.line }, horzLines: { color: c.line } },
    rightPriceScale: { borderColor: c.line },
    timeScale: { borderColor: c.line },
  };
}

function seriesOptions() {
  const c = theme();
  return { upColor: c.gain, downColor: c.loss, wickUpColor: c.gain, wickDownColor: c.loss };
}

type Props = {
  symbol: string;
  granularity: number;
  decimals: number;
  market: Market;
  positions: Position[];
  locale: Locale;
  messages: Messages;
};

/** Bougies du backend, dernière bougie animée par les ticks. Affichage seulement. */
export function PriceChart({ symbol, granularity, decimals, market, positions, locale, messages }: Props) {
  const t = messages.trading.chart;
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const series = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const last = useRef<Bar | null>(null);
  const lines = useRef<IPriceLine[]>([]);
  const [ready, setReady] = useState(false);
  const [state, setState] = useState<"loading" | "ready" | "empty">("loading");
  const [version, setVersion] = useState(0);
  const { onTick, onGap } = market;

  useEffect(() => {
    let disposed = false;
    const element = host.current;
    const observer = new MutationObserver(() => {
      chart.current?.applyOptions(chartOptions());
      series.current?.applyOptions(seriesOptions());
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    void import("lightweight-charts").then(({ CandlestickSeries, ColorType, CrosshairMode, createChart }) => {
      if (disposed || !element) return;
      const f = formatters(locale);
      const created = createChart(element, {
        autoSize: true,
        layout: { background: { type: ColorType.Solid, color: "transparent" }, fontFamily: getComputedStyle(element).fontFamily, fontSize: 12 },
        crosshair: { mode: CrosshairMode.Normal },
        timeScale: {
          timeVisible: true,
          secondsVisible: false,
          rightOffset: 4,
          tickMarkFormatter: (time: number) => f.time(new Date(time * 1000)),
        },
        localization: { timeFormatter: (time: number) => f.dateTime(new Date(time * 1000)) },
      });
      created.applyOptions(chartOptions());
      const candles = created.addSeries(CandlestickSeries, {
        ...seriesOptions(),
        borderVisible: false,
        priceFormat: { type: "price", precision: decimals, minMove: 10 ** -decimals },
      });
      chart.current = created;
      series.current = candles;
      setReady(true);
    });

    return () => {
      disposed = true;
      observer.disconnect();
      chart.current?.remove();
      chart.current = null;
      series.current = null;
    };
  }, [decimals, locale]);

  useEffect(() => {
    if (!ready) return;
    let stopped = false;
    let first = true;

    async function load() {
      const result = await api<{ candles: Candle[] }>(`/market/candles?symbol=${encodeURIComponent(symbol)}&granularity=${granularity}`);
      if (stopped || !series.current) return;
      if (!result.ok) {
        if (first) setState("empty");
        return;
      }
      const bars = result.data.candles.map((c) => ({ ...c, time: c.epoch as UTCTimestamp }));
      series.current.setData(bars);
      last.current = bars.at(-1) ?? null;
      if (first) {
        first = false;
        chart.current?.timeScale().setVisibleLogicalRange({ from: Math.max(0, bars.length - VISIBLE_BARS), to: bars.length + 4 });
      }
      setState(bars.length ? "ready" : "empty");
    }

    void load();
    const timer = setInterval(() => void load(), REFRESH_MS);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [ready, symbol, granularity, version]);

  // Trou signalé par le backend : les bougies sont relues, jamais extrapolées ici.
  useEffect(() => onGap((gap) => gap === symbol && setVersion((value) => value + 1)), [onGap, symbol]);

  useEffect(
    () =>
      onTick((tick: Tick) => {
        if (tick.symbol !== symbol || !series.current || !last.current) return;
        const time = (Math.floor(tick.epoch / granularity) * granularity) as UTCTimestamp;
        if (time < last.current.time) return;
        const bar: Bar =
          time === last.current.time
            ? {
                ...last.current,
                high: Math.max(last.current.high, tick.quote),
                low: Math.min(last.current.low, tick.quote),
                close: tick.quote,
              }
            : { time, open: tick.quote, high: tick.quote, low: tick.quote, close: tick.quote };
        last.current = bar;
        series.current.update(bar);
      }),
    [onTick, symbol, granularity],
  );

  const key = positions
    .filter((p) => p.symbol === symbol)
    .map((p) => `${p.id}:${p.entry_spot}:${p.stop_spot}`)
    .join("|");

  useEffect(() => {
    const target = series.current;
    if (!ready || !target) return;
    const c = theme();
    lines.current.forEach((line) => target.removePriceLine(line));
    lines.current = positions
      .filter((p) => p.symbol === symbol)
      .flatMap((p) => [
        p.entry_spot && { price: Number(p.entry_spot), color: c.fg, lineWidth: 1 as const, lineStyle: 2, title: t.entry, axisLabelVisible: true },
        p.stop_spot && { price: Number(p.stop_spot), color: c.loss, lineWidth: 1 as const, lineStyle: 2, title: t.stop, axisLabelVisible: true },
      ])
      .filter((line) => !!line)
      .map((line) => target.createPriceLine(line));
    // La clé résume les niveaux : les autres champs changent à chaque lecture.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, ready, symbol, t.entry, t.stop]);

  return (
    <div className="relative h-[44dvh] min-h-64 w-full sm:h-[420px] lg:h-[460px]">
      <div ref={host} className="absolute inset-0" />
      {state !== "ready" && (
        <div role="status" className="absolute inset-0 grid place-items-center bg-card text-muted">
          {state === "loading" ? (
            <span className="inline-flex items-center gap-2">
              <LoaderCircle size={20} strokeWidth={1.5} aria-hidden className="animate-spin" />
              {t.loading}
            </span>
          ) : (
            <span className="max-w-xs px-4 text-center">{t.empty}</span>
          )}
        </div>
      )}
    </div>
  );
}
