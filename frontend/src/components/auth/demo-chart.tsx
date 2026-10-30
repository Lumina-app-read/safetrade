import { ShieldCheck, TrendingUp } from "lucide-react";

import type { Messages } from "@/i18n/messages";

// Série fixe et fictive (données de démonstration, jamais présentées comme réelles).
const POINTS = [42, 44, 43, 47, 46, 49, 48, 52, 50, 53, 55, 54, 57, 56, 59, 61, 60, 63];

function path(width: number, height: number): string {
  const min = Math.min(...POINTS);
  const max = Math.max(...POINTS);
  return POINTS.map((p, i) => {
    const x = (i / (POINTS.length - 1)) * width;
    const y = height - 8 - ((p - min) / (max - min)) * (height - 16);
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

/** Carte de session fictive animée, pour le panneau visuel des pages d'authentification. */
export function DemoSessionCard({ messages, result }: { messages: Messages["auth"]; result: string }) {
  const d = path(320, 96);
  return (
    <div className="relative rounded-xl border border-on-anthracite/10 bg-on-anthracite/5 p-5 backdrop-blur-sm">
      <div className="flex items-center justify-between gap-3">
        <span className="text-label font-medium">{messages.demoSession}</span>
        <span className="rounded-full border border-on-anthracite/20 px-2.5 py-0.5 text-small text-on-anthracite/70">
          {messages.demoData}
        </span>
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-small text-on-anthracite/60">{messages.demoResult}</span>
        <span className="inline-flex items-center gap-1 text-kpi font-medium text-gain-on-dark tabular-nums">
          <TrendingUp size={20} strokeWidth={1.5} aria-hidden />+{result}
        </span>
      </div>
      <svg viewBox="0 0 320 96" className="mt-3 h-24 w-full overflow-visible" aria-hidden>
        <defs>
          <linearGradient id="demo-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="currentColor" stopOpacity="0.25" />
            <stop offset="1" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={`${d} L320,96 L0,96 Z`} fill="url(#demo-fill)" className="animate-fade text-accent" />
        <path
          d={d}
          fill="none"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          pathLength={1000}
          strokeDasharray={1000}
          className="animate-draw stroke-on-anthracite"
        />
      </svg>
      <div className="mt-3 flex items-center gap-2 text-small text-on-anthracite/70">
        <span className="size-2 animate-pulse-dot rounded-full bg-gain-on-dark" aria-hidden />
        <ShieldCheck size={16} strokeWidth={1.5} aria-hidden />
        {messages.demoProtection}
      </div>
    </div>
  );
}
