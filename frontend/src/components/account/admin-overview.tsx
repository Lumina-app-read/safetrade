"use client";

import { Activity, Bot, CircleAlert, Coins, Gift, LineChart, OctagonAlert, UserPlus, Users } from "lucide-react";
import Link from "next/link";

import { usePolled } from "@/components/trading/use-live";
import { useAdmin } from "@/components/shell/admin-shell";
import { Alert } from "@/components/ui/alert";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { errorMessage } from "@/lib/api";

import { AdminTitle, StatTile } from "./admin-ui";

type Stats = {
  users: number;
  new_users_7d: number;
  active_users_7d: number;
  trials: number;
  subscribers: number;
  bots: number;
  bot_errors_24h: number;
  open_positions: number;
  halted: boolean;
  revenue_30d?: Array<{ currency: string; amount: string; count: number }>;
};

/** Tableau de bord de l'équipe : chiffres calculés par le serveur, relus toutes les 30 secondes. */
export function AdminOverview({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.adminOverview;
  const f = formatters(locale);
  const { user, permissions } = useAdmin();
  const stats = usePolled<Stats>("/admin/stats", 30000);
  const s = stats.data;
  const revenue = s?.revenue_30d;
  const revenueText =
    revenue === undefined
      ? null
      : revenue.length === 0
        ? f.money(0)
        : revenue.map((r) => f.moneyShort(Number(r.amount), r.currency)).join(" · ");

  return (
    <>
      <AdminTitle title={interpolate(t.title, { name: user.first_name })} subtitle={t.subtitle} />

      {s?.halted && (
        <div className="mt-6">
          <Alert tone="error">
            <span className="inline-flex flex-wrap items-center gap-2">
              <OctagonAlert size={18} strokeWidth={1.5} aria-hidden />
              {t.halted}
              {permissions.includes("risk.write") && (
                <Link href={`/${locale}/admin/trading`} className="font-medium underline underline-offset-4">
                  {t.haltedAction}
                </Link>
              )}
            </span>
          </Alert>
        </div>
      )}
      {stats.error && !s && (
        <div className="mt-6">
          <Alert tone="error">{errorMessage(messages, stats.error)}</Alert>
        </div>
      )}

      <div className="mt-6 grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatTile label={t.users} value={s ? f.number(s.users) : t.loading} icon={Users} />
        <StatTile label={t.newUsers} value={s ? f.number(s.new_users_7d) : t.loading} icon={UserPlus} hint={t.last7} />
        <StatTile label={t.activeUsers} value={s ? f.number(s.active_users_7d) : t.loading} icon={Activity} hint={t.last7} />
        <StatTile label={t.trials} value={s ? f.number(s.trials) : t.loading} icon={Gift} />
        <StatTile label={t.subscribers} value={s ? f.number(s.subscribers) : t.loading} icon={LineChart} />
        {revenueText !== null && (
          <StatTile label={t.revenue} value={s ? revenueText : t.loading} icon={Coins} hint={t.last30} />
        )}
        <StatTile
          label={t.bots}
          value={s ? f.number(s.bots) : t.loading}
          icon={Bot}
          hint={s ? interpolate(t.openPositions, { count: s.open_positions }) : undefined}
        />
        <StatTile label={t.errors} value={s ? f.number(s.bot_errors_24h) : t.loading} icon={CircleAlert} hint={t.last24} />
      </div>
    </>
  );
}
