import { Bot, ShieldCheck, TrendingUp, Wifi } from "lucide-react";

import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import type { Messages } from "@/i18n/messages";

// Série fixe et fictive : données de démonstration, jamais présentées comme réelles.
const SERIES = [
  61, 63, 62, 65, 64, 66, 63, 61, 64, 67, 69, 68, 66, 69, 72, 71, 73, 70, 72, 75, 74, 77, 76, 74, 77, 80, 79,
  81, 83, 82,
];

function chartPath(width: number, height: number) {
  const min = Math.min(...SERIES) - 2;
  const max = Math.max(...SERIES) + 2;
  const pts = SERIES.map((v, i) => [
    (i / (SERIES.length - 1)) * width,
    height - ((v - min) / (max - min)) * height,
  ]);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const last = pts[pts.length - 1] ?? [width, 0];
  return { line, area: `${line} L${width},${height} L0,${height} Z`, last };
}

/**
 * Composition d'interface de trading (CSS et SVG) : repli du visuel du hero tant que
 * public/images/hero.* n'est pas déposé. Toujours marquée « Données de démonstration ».
 */
export function TradingPreview({ locale, messages }: { locale: Locale; messages: Messages["landing"]["preview"] }) {
  const f = formatters(locale);
  const { line, area, last } = chartPath(560, 180);
  return (
    <div className="relative">
      <div
        aria-hidden
        className="absolute -inset-8 -z-10 rounded-[40px] bg-[radial-gradient(60%_60%_at_60%_40%,var(--brand-ring),transparent_70%)] opacity-70 blur-2xl"
      />
      <div
        role="img"
        aria-label={`${messages.asset} · ${messages.demo}`}
        className="overflow-hidden rounded-2xl border border-line bg-card shadow-[0_30px_80px_-30px_var(--brand-ring)]"
      >
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent-text">
              <TrendingUp size={16} strokeWidth={1.5} aria-hidden />
            </span>
            <span className="truncate text-label font-medium">{messages.asset}</span>
            <span className="rounded-md border border-warn-line px-1.5 py-0.5 text-[11px] font-medium text-warn">
              {messages.mode}
            </span>
          </div>
          <span className="flex shrink-0 items-center gap-1.5 text-small text-muted">
            <Wifi size={14} strokeWidth={1.5} aria-hidden className="text-gain" />
            <span className="max-sm:hidden">{messages.connected}</span>
          </span>
        </div>

        <div className="px-4 pt-4 sm:px-5">
          <div className="flex items-end justify-between gap-3">
            <div>
              <div className="text-kpi font-medium tabular-nums">{f.number(4182.37)}</div>
              <div className="text-small text-gain tabular-nums">{f.percent(0.0084, 2, true)}</div>
            </div>
            <span className="flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-small">
              <span className="size-2 animate-pulse-dot rounded-full bg-gain" aria-hidden />
              {messages.botState}
            </span>
          </div>
          <svg viewBox="0 0 560 180" className="mt-3 h-36 w-full overflow-visible sm:h-44" preserveAspectRatio="none" aria-hidden>
            <defs>
              <linearGradient id="preview-fill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0" stopColor="var(--fg)" stopOpacity="0.12" />
                <stop offset="1" stopColor="var(--fg)" stopOpacity="0" />
              </linearGradient>
            </defs>
            {[45, 90, 135].map((y) => (
              <line key={y} x1="0" x2="560" y1={y} y2={y} stroke="var(--line)" strokeDasharray="4 6" />
            ))}
            <path d={area} fill="url(#preview-fill)" className="animate-fade" />
            <path
              d={line}
              fill="none"
              stroke="var(--fg)"
              strokeWidth="1.75"
              strokeLinejoin="round"
              vectorEffect="non-scaling-stroke"
              pathLength={1000}
              strokeDasharray={1000}
              className="animate-draw"
            />
            <circle cx={last[0]} cy={last[1]} r="4" fill="var(--accent)" className="animate-pulse-dot" />
          </svg>
        </div>

        <div className="grid grid-cols-2 gap-px border-t border-line bg-line sm:grid-cols-3">
          <div className="bg-card px-4 py-3 sm:px-5">
            <div className="text-small text-muted">{messages.today}</div>
            <div className="mt-0.5 font-medium text-gain tabular-nums">+{f.money(12.4)}</div>
          </div>
          <div className="bg-card px-4 py-3 sm:px-5">
            <div className="text-small text-muted">{messages.openPositions}</div>
            <div className="mt-0.5 font-medium tabular-nums">1</div>
          </div>
          <div className="col-span-2 bg-card px-4 py-3 sm:col-span-1 sm:px-5">
            <div className="flex justify-between text-small text-muted">
              {messages.riskUsed}
              <span className="tabular-nums">{f.percent(0.18)}</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-page">
              <div className="h-full w-[18%] rounded-full bg-gain" />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-3 text-small sm:px-5">
          <span className="flex items-center gap-1.5 text-muted">
            <ShieldCheck size={14} strokeWidth={1.5} aria-hidden />
            {messages.stopLoss}
          </span>
          <span className="rounded-full bg-page px-2.5 py-0.5 text-muted">{messages.demo}</span>
        </div>
      </div>

      {/* Carte flottante : décision du moteur, visible à partir de la tablette. */}
      <div className="absolute -bottom-6 -left-6 hidden animate-rise items-center gap-3 rounded-xl border border-line bg-card/95 px-4 py-3 shadow-[0_20px_40px_-20px_var(--brand-ring)] backdrop-blur [animation-delay:600ms] md:flex">
        <span className="grid size-9 place-items-center rounded-lg bg-gain-soft text-gain">
          <Bot size={18} strokeWidth={1.5} aria-hidden />
        </span>
        <div>
          <div className="text-small text-muted">{messages.netGain}</div>
          <div className="font-medium text-gain tabular-nums">+{f.money(0.18)}</div>
        </div>
      </div>
    </div>
  );
}
