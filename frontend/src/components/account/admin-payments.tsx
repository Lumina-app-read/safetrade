"use client";

import { RefreshCw, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";

import { AdminTitle, type ApiErr } from "./admin-ui";
import { planName } from "./admin-users";

type Order = {
  id: string;
  user_id: string;
  email: string;
  plan: string;
  provider: string;
  amount: string;
  currency: string;
  status: string;
  reference: string | null;
  paid_amount: string | null;
  paid_currency: string | null;
  created_at: string;
  paid_at: string | null;
};

const STATUSES = ["all", "paid", "pending", "partial", "failed", "expired"] as const;
const TONE: Record<string, BadgeTone> = { paid: "gain", pending: "warn", partial: "loss", failed: "loss", expired: "neutral" };

/** Transactions des fournisseurs. Le rapprochement relit l'état chez le fournisseur, rien n'est saisi ici. */
export function AdminPayments({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.adminPayments;
  const f = formatters(locale);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<(typeof STATUSES)[number]>("all");
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<ApiErr | null>(null);
  const [checking, setChecking] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ limit: "100" });
      if (query.trim()) params.set("q", query.trim());
      if (status !== "all") params.set("status", status);
      api<{ orders: Order[] }>(`/admin/payments?${params}`).then((result) => {
        if (!active) return;
        if (result.ok) {
          setOrders(result.data.orders);
          setError(null);
        } else setError(result);
      });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query, status, version]);

  async function check(order: Order) {
    setChecking(order.id);
    setNotice(null);
    const result = await api<{ provider_status: string }>(`/admin/payments/${order.id}/check`, { method: "POST" });
    setChecking(null);
    if (result.ok) {
      setNotice({ tone: "success", text: interpolate(t.checked, { status: result.data.provider_status }) });
      setVersion((v) => v + 1);
    } else setNotice({ tone: "error", text: errorMessage(messages, result) });
  }

  return (
    <>
      <AdminTitle title={messages.admin.payments} subtitle={t.subtitle} />
      <div className="mt-6 flex flex-col gap-3">
        <Field
          label={t.search}
          icon={Search}
          placeholder={t.searchPlaceholder}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          type="search"
          inputMode="search"
          autoComplete="off"
          maxLength={100}
        />
        <div role="group" aria-label={t.filter} className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none]">
          {STATUSES.map((key) => (
            <button
              key={key}
              type="button"
              aria-pressed={status === key}
              onClick={() => setStatus(key)}
              className="h-11 shrink-0 rounded-lg border border-line bg-card px-4 text-label font-medium aria-pressed:border-accent aria-pressed:bg-accent aria-pressed:text-on-accent"
            >
              {key === "all" ? t.all : t.statuses[key]}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-4 flex flex-col gap-3">
        {notice && <Alert tone={notice.tone}>{notice.text}</Alert>}
        {error && <Alert tone="error">{errorMessage(messages, error)}</Alert>}
      </div>

      <Card className="mt-4 p-2 sm:p-3">
        {orders === null && !error && <p className="p-3 text-muted">{messages.trading.loading}</p>}
        {orders?.length === 0 && <p className="p-3 text-muted">{t.empty}</p>}
        <ul className="divide-y divide-line">
          {orders?.map((order) => (
            <li key={order.id} className="flex flex-col gap-3 px-2 py-3 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium tabular-nums">{f.money(Number(order.amount), order.currency)}</span>
                  <span className="text-muted">{planName(messages, order.plan)}</span>
                  <Badge tone={TONE[order.status] ?? "neutral"}>
                    {t.statuses[order.status as keyof typeof t.statuses] ?? order.status}
                  </Badge>
                </div>
                <Link
                  href={`/${locale}/admin/users/sheet?id=${order.user_id}`}
                  className="mt-1 block truncate text-small text-accent-text underline-offset-4 hover:underline"
                >
                  {order.email}
                </Link>
                <p className="mt-0.5 text-small text-muted">
                  {[
                    t.providers[order.provider as keyof typeof t.providers] ?? order.provider,
                    f.dateTime(order.created_at),
                    order.paid_amount && order.paid_currency
                      ? interpolate(t.paidIn, { amount: f.money(Number(order.paid_amount), order.paid_currency) })
                      : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              {order.reference && order.status !== "paid" && (
                <Button type="button" pending={checking === order.id} onClick={() => check(order)} className="self-start sm:self-center">
                  <RefreshCw size={16} strokeWidth={1.5} aria-hidden />
                  {checking === order.id ? t.checking : t.check}
                </Button>
              )}
            </li>
          ))}
        </ul>
      </Card>
      <p className="mt-3 text-small text-muted">{t.refundNote}</p>
    </>
  );
}
