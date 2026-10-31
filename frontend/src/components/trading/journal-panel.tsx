"use client";

import {
  Ban,
  Bot,
  CircleAlert,
  CircleCheck,
  CircleDot,
  Gauge,
  Link2Off,
  RefreshCw,
  Shield,
  ScrollText,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import type { Messages } from "@/i18n/messages";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";

import { codeText } from "./labels";
import { closeReason } from "./positions-panel";
import type { Decision } from "./types";
import { usePolled } from "./use-live";

const REFRESH_MS = 5000;

const ICONS: Record<string, { icon: LucideIcon; tone: string }> = {
  signal: { icon: Gauge, tone: "text-muted" },
  order_refused: { icon: Ban, tone: "text-warn" },
  order_void: { icon: Ban, tone: "text-warn" },
  order_unknown: { icon: CircleAlert, tone: "text-warn" },
  position_open: { icon: CircleDot, tone: "text-fg" },
  position_closed: { icon: CircleCheck, tone: "text-fg" },
  floor_set: { icon: Shield, tone: "text-gain" },
  floor_refused: { icon: Shield, tone: "text-warn" },
  stop_missing: { icon: CircleAlert, tone: "text-loss" },
  reconciled: { icon: RefreshCw, tone: "text-muted" },
  reconcile_adopted: { icon: RefreshCw, tone: "text-warn" },
  reconcile_foreign: { icon: CircleAlert, tone: "text-muted" },
  error: { icon: Link2Off, tone: "text-loss" },
  broker_error: { icon: Link2Off, tone: "text-warn" },
};

/** Journal des décisions, lu tel qu'écrit par le moteur (table en ajout seul). */
export function JournalPanel({ locale, messages, limit = 100 }: { locale: Locale; messages: Messages; limit?: number }) {
  const t = messages.trading.journal;
  const f = formatters(locale);
  const [showIdle, setShowIdle] = useState(false);
  const { data, error, loading } = usePolled<{ decisions: Decision[] }>(
    `/trading/decisions?limit=${limit}&hide_idle=${!showIdle}`,
    REFRESH_MS,
  );
  const rows = data?.decisions ?? [];
  const kinds = t.kinds as Record<string, string>;

  return (
    <div className="flex flex-col gap-2">
      <Checkbox label={t.showIdle} checked={showIdle} onChange={(event) => setShowIdle(event.target.checked)} />
      {error && !data && <Alert tone="error">{errorMessage(messages, error)}</Alert>}
      {loading && <p className="py-8 text-center text-muted">{messages.trading.loading}</p>}
      {!loading && rows.length === 0 && !error && (
        <div className="flex flex-col items-center gap-2 py-10 text-center">
          <span className="grid size-11 place-items-center rounded-xl bg-page text-muted">
            <ScrollText size={20} strokeWidth={1.5} aria-hidden />
          </span>
          <p className="font-medium">{t.emptyTitle}</p>
          <p className="max-w-sm text-small text-muted">{t.emptyBody}</p>
        </div>
      )}
      <ol className="flex flex-col">
        {rows.map((row) => {
          const { icon: Icon, tone } = ICONS[row.kind] ?? { icon: Bot, tone: "text-muted" };
          const net = row.kind === "position_closed" ? Number(row.data.net_result) : null;
          // Le code d'une vente est son motif ; un code inconnu n'apprend rien au client.
          const text = row.kind === "sell_sent" ? closeReason(messages, row.code) : codeText(messages, row.code);
          const detail = text === messages.trading.codes.unknown ? "" : text;
          return (
            <li key={row.id} className="flex items-start gap-3 border-b border-line py-3 last:border-b-0">
              <Icon size={16} strokeWidth={1.5} aria-hidden className={cn("mt-0.5 shrink-0", tone)} />
              <div className="min-w-0 flex-1">
                <p className="font-medium">{kinds[row.kind] ?? t.other}</p>
                {detail && <p className="text-small text-muted">{detail}</p>}
                {net !== null && !Number.isNaN(net) && <p className="text-small text-muted tabular-nums">{`${t.net} ${f.money(net)}`}</p>}
              </div>
              <time dateTime={row.at} className="shrink-0 text-small text-muted tabular-nums">
                {f.time(row.at)}
              </time>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
