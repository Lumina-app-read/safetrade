import { ShieldAlert } from "lucide-react";

import { Card } from "@/components/ui/card";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { cn } from "@/lib/cn";

import { usage } from "./labels";
import type { RiskUsage } from "./types";

function Meter({ label, value, share, danger }: { label: string; value: string; share: number; danger?: boolean }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <span className="text-label font-medium">{label}</span>
        <span className="text-small whitespace-nowrap text-muted tabular-nums">{value}</span>
      </div>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(share * 100)}
        className="h-1.5 overflow-hidden rounded-full bg-page"
      >
        <div
          className={cn("h-full rounded-full transition-[width] duration-500", danger && share >= 0.75 ? "bg-loss" : share >= 0.5 ? "bg-warn-line" : "bg-primary")}
          style={{ width: `${Math.max(share * 100, share > 0 ? 3 : 0)}%` }}
        />
      </div>
    </div>
  );
}

/** Consommation des limites, en montants calculés par le backend. */
export function RiskPanel({ risk, locale, messages }: { risk: RiskUsage | null; locale: Locale; messages: Messages }) {
  const t = messages.trading.risk;
  const f = formatters(locale);
  const money = (value: string | number) => f.money(Number(value));

  if (!risk) {
    return (
      <Card className="flex flex-col gap-2 p-5">
        <h2 className="flex items-center gap-2 text-h3 font-medium">
          <ShieldAlert size={20} strokeWidth={1.5} aria-hidden className="text-muted" />
          {t.title}
        </h2>
        <p className="text-muted">{t.empty}</p>
      </Card>
    );
  }

  const sessionLoss = Math.max(0, -Number(risk.session_net));
  const dayLoss = Math.max(0, -Number(risk.day_net));
  return (
    <Card className="flex flex-col gap-4 p-5">
      <h2 className="flex items-center gap-2 text-h3 font-medium">
        <ShieldAlert size={20} strokeWidth={1.5} aria-hidden className="text-muted" />
        {t.title}
      </h2>
      <Meter danger label={t.sessionLoss} value={`${money(sessionLoss)} / ${money(risk.session_loss_limit)}`} share={usage(sessionLoss, Number(risk.session_loss_limit))} />
      <Meter danger label={t.dayLoss} value={`${money(dayLoss)} / ${money(risk.day_loss_limit)}`} share={usage(dayLoss, Number(risk.day_loss_limit))} />
      <Meter label={t.exposure} value={`${money(risk.exposure)} / ${money(risk.exposure_limit)}`} share={usage(Number(risk.exposure), Number(risk.exposure_limit))} />
      <Meter label={t.losses} value={`${risk.consecutive_losses} / ${risk.max_consecutive_losses}`} share={usage(risk.consecutive_losses, risk.max_consecutive_losses)} />
      <p className="text-small text-muted">
        {interpolate(t.slippage, {
          stop: money(risk.stop_loss),
          worst: money(risk.worst_case_loss),
          margin: f.percent(Number(risk.slippage_margin)),
        })}
      </p>
    </Card>
  );
}
