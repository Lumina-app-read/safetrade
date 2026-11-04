"use client";

import {
  ArrowLeft,
  CalendarDays,
  ChevronRight,
  LogOut,
  NotebookPen,
  Search,
  ShieldOff,
  UserCheck,
  UserX,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { useAdmin } from "@/components/shell/admin-shell";
import { Alert } from "@/components/ui/alert";
import { SignedAmount } from "@/components/ui/amount";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, SectionTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useFormErrors } from "@/lib/use-form-errors";

import { AdminTitle, Fact, ReasonAction, type ApiErr } from "./admin-ui";

type Access = { status: "trial" | "active" | "expired" | "suspended" | "none"; plan: string; ends_at: string | null };
type UserRow = { id: string; email: string; first_name: string; role: string; status: string; access: Access };
type Period = {
  id: string;
  plan: string;
  source: "trial" | "manual" | "payment";
  starts_at: string;
  ends_at: string;
  granted_by: string | null;
  note: string | null;
  revoked_at: string | null;
};
type Profile = {
  id: string;
  email: string;
  first_name: string;
  role: string;
  status: string;
  locale: string;
  email_verified: boolean;
  mfa_enabled: boolean;
  created_at: string;
  last_seen_at: string | null;
  open_sessions: number;
};
type Bot = {
  id: string;
  symbol: string;
  account_kind: string;
  state: string;
  stop_reason: string | null;
  started_at: string;
  ended_at: string | null;
};
type Order = { id: string; plan: string; provider: string; amount: string; currency: string; status: string; created_at: string };
type Sheet = {
  profile: Profile;
  access: Access;
  history: Period[];
  trading: {
    deriv: { account_id: string | null; account_kind: string | null; currency: string | null; method: string; connected_at: string } | null;
    bots: Bot[];
    closed_positions: number;
    net_result: string;
  };
  payments: Order[] | null;
  affiliation: { affiliate_status: string | null; affiliate_code: string | null; referred_by: string | null };
};
type AccessUpdate = { access: Access; history: Period[] };

const TONE: Record<Access["status"], BadgeTone> = {
  active: "gain",
  trial: "brand",
  expired: "warn",
  suspended: "loss",
  none: "neutral",
};
const FILTERS = ["all", "active", "suspended"] as const;

export function planName(messages: Messages, code: string): string {
  return messages.plans.levels[code as keyof Messages["plans"]["levels"]] ?? code;
}

export function roleName(messages: Messages, role: string): string {
  return messages.adminUsers.roles[role as keyof Messages["adminUsers"]["roles"]] ?? role;
}

function AccessBadge({ access, messages }: { access: Access; messages: Messages }) {
  const label = messages.adminUsers.statuses[access.status];
  const plan = access.status === "active" ? ` · ${planName(messages, access.plan)}` : "";
  return (
    <span className="shrink-0">
      <Badge tone={TONE[access.status]}>{`${label}${plan}`}</Badge>
    </span>
  );
}

/** Liste des comptes ; la fiche complète s'ouvre sur sa propre page. */
export function AdminUsers({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.adminUsers;
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const [users, setUsers] = useState<UserRow[] | null>(null);
  const [error, setError] = useState<ApiErr | null>(null);

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ limit: "100" });
      if (query.trim()) params.set("q", query.trim());
      if (filter !== "all") params.set("status", filter);
      api<{ users: UserRow[] }>(`/admin/users?${params}`).then((result) => {
        if (!active) return;
        if (result.ok) {
          setUsers(result.data.users);
          setError(null);
        } else setError(result);
      });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query, filter]);

  return (
    <>
      <AdminTitle title={messages.admin.users} subtitle={t.subtitle} />
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
          enterKeyHint="search"
          maxLength={100}
        />
        <div role="group" aria-label={t.filter} className="flex flex-wrap gap-2">
          {FILTERS.map((key) => (
            <button
              key={key}
              type="button"
              aria-pressed={filter === key}
              onClick={() => setFilter(key)}
              className="h-11 rounded-lg border border-line bg-card px-4 text-label font-medium aria-pressed:border-accent aria-pressed:bg-accent aria-pressed:text-on-accent"
            >
              {t.filters[key]}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="mt-4">
          <Alert tone="error">{errorMessage(messages, error)}</Alert>
        </div>
      )}

      <Card className="mt-4 p-2 sm:p-3">
        {users === null && !error && <p className="p-3 text-muted">{messages.trading.loading}</p>}
        {users?.length === 0 && <p className="p-3 text-muted">{t.empty}</p>}
        <ul className="divide-y divide-line">
          {users?.map((user) => (
            <li key={user.id}>
              <Link
                href={`/${locale}/admin/users/sheet?id=${user.id}`}
                className="flex min-h-16 w-full items-center gap-3 rounded-lg px-2 py-2.5 hover:bg-page"
              >
                <span className="grid size-10 shrink-0 place-items-center rounded-full bg-page text-label font-medium uppercase">
                  {user.first_name.slice(0, 1)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{user.first_name}</span>
                  <span className="block truncate text-small text-muted">{user.email}</span>
                </span>
                {user.role !== "client" && (
                  <span className="max-sm:hidden">
                    <Badge tone="neutral">{roleName(messages, user.role)}</Badge>
                  </span>
                )}
                <AccessBadge access={user.access} messages={messages} />
                <ChevronRight size={16} strokeWidth={1.5} aria-hidden className="shrink-0 text-muted" />
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}

/** Fiche complète d'un compte : profil, accès, trading, paiements, affiliation et actions. */
export function AdminUserSheet({ locale, messages }: { locale: Locale; messages: Messages }) {
  const userId = useSearchParams().get("id") ?? "";
  const t = messages.adminUsers;
  const f = formatters(locale);
  const { permissions, user: me } = useAdmin();
  const canGrant = permissions.includes("subscriptions.write");
  const canAct = permissions.includes("users.write");
  const [sheet, setSheet] = useState<Sheet | null>(null);
  const [error, setError] = useState<ApiErr | null>(null);

  useEffect(() => {
    let active = true;
    api<Sheet>(`/admin/users/${userId}`).then((result) => {
      if (!active) return;
      if (result.ok) setSheet(result.data);
      else setError(result);
    });
    return () => {
      active = false;
    };
  }, [userId]);

  const back = (
    <Link href={`/${locale}/admin/users`} className="inline-flex min-h-11 items-center gap-1.5 text-label text-muted hover:text-fg">
      <ArrowLeft size={16} strokeWidth={1.5} aria-hidden />
      {t.back}
    </Link>
  );
  if (error) {
    return (
      <>
        {back}
        <Alert tone="error">{errorMessage(messages, error)}</Alert>
      </>
    );
  }
  if (!sheet) return <p className="text-muted">{messages.trading.loading}</p>;

  const { profile, trading, affiliation } = sheet;
  const update = (next: Partial<Sheet>) => setSheet({ ...sheet, ...next });
  const last = sheet.history.find((period) => !period.revoked_at);
  const suspended = profile.status === "suspended";
  const protectedAccount = profile.id === me.id || profile.role === "super_admin";
  const net = Number(trading.net_result);

  return (
    <>
      {back}
      <div className="mt-2 flex flex-wrap items-center gap-4">
        <span className="grid size-14 shrink-0 place-items-center rounded-full bg-accent-soft text-h3 font-medium text-accent-text uppercase">
          {profile.first_name.slice(0, 1)}
        </span>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-h1">{profile.first_name}</h1>
          <p className="truncate text-muted">{profile.email}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={suspended ? "loss" : "gain"}>{suspended ? t.accountSuspended : t.accountActive}</Badge>
          <AccessBadge access={sheet.access} messages={messages} />
        </div>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card className="p-5 sm:p-6">
          <h2 className="text-h3 font-medium">{t.profile}</h2>
          <dl className="mt-2 divide-y divide-line">
            <Fact label={t.role}>{roleName(messages, profile.role)}</Fact>
            <Fact label={t.language}>{profile.locale.toUpperCase()}</Fact>
            <Fact label={t.emailVerified}>{profile.email_verified ? t.yes : t.no}</Fact>
            <Fact label={t.mfa}>{profile.mfa_enabled ? t.yes : t.no}</Fact>
            <Fact label={t.createdAt}>{f.dateTime(profile.created_at)}</Fact>
            <Fact label={t.lastSeen}>{profile.last_seen_at ? f.relative(profile.last_seen_at) : t.never}</Fact>
            <Fact label={t.openSessions}>{f.number(profile.open_sessions)}</Fact>
          </dl>
        </Card>

        <Card className="p-5 sm:p-6">
          <h2 className="text-h3 font-medium">{t.trading}</h2>
          <dl className="mt-2 divide-y divide-line">
            <Fact label={t.deriv}>
              {trading.deriv
                ? `${trading.deriv.account_id ?? t.unknown} · ${trading.deriv.account_kind === "real" ? t.real : t.demo}`
                : t.notConnected}
            </Fact>
            <Fact label={t.closedPositions}>{f.number(trading.closed_positions)}</Fact>
            <Fact label={t.netResult}>
              <SignedAmount value={net} formatted={f.money(Math.abs(net), trading.deriv?.currency ?? "USD")} />
            </Fact>
            <Fact label={t.sponsor}>{affiliation.referred_by ?? t.none}</Fact>
            <Fact label={t.affiliate}>
              {affiliation.affiliate_status
                ? `${t.affiliateStatuses[affiliation.affiliate_status as keyof typeof t.affiliateStatuses] ?? affiliation.affiliate_status}${affiliation.affiliate_code ? ` · ${affiliation.affiliate_code}` : ""}`
                : t.none}
            </Fact>
          </dl>
          <p className="mt-3 text-small text-muted">{t.tokenNote}</p>
        </Card>
      </div>

      {canAct && !protectedAccount && (
        <>
          <SectionTitle>{t.actions}</SectionTitle>
          <Card className="flex flex-col gap-3 p-5 sm:flex-row sm:flex-wrap sm:items-start sm:p-6">
            {suspended ? (
              <ReasonAction
                messages={messages}
                label={t.reactivate}
                confirm={t.confirmReactivate}
                pending={t.working}
                icon={UserCheck}
                variant="primary"
                onSubmit={(note) => api<Pick<Sheet, "profile" | "access">>(`/admin/users/${userId}/reactivate`, { body: { note } })}
                onDone={update}
              />
            ) : (
              <ReasonAction
                messages={messages}
                label={t.suspend}
                confirm={t.confirmSuspend}
                pending={t.working}
                icon={UserX}
                variant="danger"
                onSubmit={(note) => api<Pick<Sheet, "profile" | "access">>(`/admin/users/${userId}/suspend`, { body: { note } })}
                onDone={update}
              />
            )}
            <ReasonAction
              messages={messages}
              label={t.revokeSessions}
              confirm={t.confirmRevokeSessions}
              pending={t.working}
              icon={LogOut}
              onSubmit={(note) => api<Pick<Sheet, "profile">>(`/admin/users/${userId}/sessions/revoke`, { body: { note } })}
              onDone={update}
            />
          </Card>
          <p className="mt-2 text-small text-muted">{t.suspendNote}</p>
        </>
      )}

      <SectionTitle>{t.history}</SectionTitle>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        {canGrant ? (
          <GrantForm userId={userId} plans={null} messages={messages} onDone={update} />
        ) : (
          <Alert tone="info">{t.readOnly}</Alert>
        )}
        <Card className="p-4 sm:p-5">
          <p className="text-muted">
            {sheet.access.ends_at ? interpolate(t.until, { date: f.dateTime(sheet.access.ends_at) }) : t.noAccess}
          </p>
          {sheet.history.length === 0 && <p className="mt-2 text-muted">{t.noHistory}</p>}
          <ul className="mt-3 flex flex-col gap-3">
            {sheet.history.map((period) => (
              <li key={period.id} className={cn("rounded-xl border border-line p-4", period.revoked_at && "opacity-70")}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{planName(messages, period.plan)}</span>
                  <Badge tone={period.revoked_at ? "loss" : period.source === "manual" ? "brand" : "neutral"}>
                    {period.revoked_at ? t.revoked : t.sources[period.source]}
                  </Badge>
                </div>
                <p className="mt-1 text-small text-muted">
                  {interpolate(t.period, { start: f.date(period.starts_at), end: f.date(period.ends_at) })}
                </p>
                {period.granted_by && (
                  <p className="mt-1 truncate text-small text-muted">{interpolate(t.grantedBy, { email: period.granted_by })}</p>
                )}
                {period.note && <p className="mt-2 text-small">{period.note}</p>}
                {canGrant && period.source === "manual" && !period.revoked_at && period.id === last?.id && (
                  <div className="mt-3">
                    <ReasonAction
                      messages={messages}
                      label={t.revoke}
                      confirm={t.confirmRevoke}
                      pending={t.revoking}
                      icon={ShieldOff}
                      variant="danger"
                      onSubmit={(note) =>
                        api<AccessUpdate>(`/admin/users/${userId}/subscriptions/${period.id}/revoke`, { body: { note } })
                      }
                      onDone={update}
                    />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <SectionTitle>{t.bots}</SectionTitle>
      <Card className="p-2 sm:p-3">
        {trading.bots.length === 0 && <p className="p-3 text-muted">{t.noBots}</p>}
        <ul className="divide-y divide-line">
          {trading.bots.map((bot) => (
            <li key={bot.id} className="flex flex-wrap items-center justify-between gap-2 px-2 py-3">
              <div className="min-w-0">
                <p className="font-medium">{bot.symbol}</p>
                <p className="text-small text-muted">
                  {interpolate(t.botPeriod, {
                    start: f.dateTime(bot.started_at),
                    end: bot.ended_at ? f.dateTime(bot.ended_at) : t.running,
                  })}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge tone="neutral">{bot.account_kind === "real" ? t.real : t.demo}</Badge>
                <Badge tone={bot.ended_at ? "neutral" : "gain"}>
                  {messages.adminTrading.states[bot.state as keyof Messages["adminTrading"]["states"]] ?? bot.state}
                </Badge>
              </div>
            </li>
          ))}
        </ul>
      </Card>

      {sheet.payments && (
        <>
          <SectionTitle>{t.payments}</SectionTitle>
          <Card className="p-2 sm:p-3">
            {sheet.payments.length === 0 && <p className="p-3 text-muted">{t.noPayments}</p>}
            <ul className="divide-y divide-line">
              {sheet.payments.map((order) => (
                <li key={order.id} className="flex flex-wrap items-center justify-between gap-2 px-2 py-3">
                  <div className="min-w-0">
                    <p className="font-medium">
                      {planName(messages, order.plan)} · {f.money(Number(order.amount), order.currency)}
                    </p>
                    <p className="text-small text-muted">{f.dateTime(order.created_at)}</p>
                  </div>
                  <Badge tone={order.status === "paid" ? "gain" : order.status === "pending" ? "warn" : "neutral"}>
                    {messages.adminPayments.statuses[order.status as keyof Messages["adminPayments"]["statuses"]] ?? order.status}
                  </Badge>
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}
    </>
  );
}

function GrantForm({
  userId,
  plans: given,
  messages,
  onDone,
}: {
  userId: string;
  plans: Array<{ code: string; days: number }> | null;
  messages: Messages;
  onDone: (next: AccessUpdate) => void;
}) {
  const t = messages.adminUsers;
  const [plans, setPlans] = useState(given);
  const [plan, setPlan] = useState(given?.[0]?.code ?? "");
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ApiErr | null>(null);
  const [saved, setSaved] = useState(false);
  const days = plans?.find((p) => p.code === plan)?.days ?? 7;
  const { field, validate } = useFormErrors({
    days: (value) =>
      !value.trim() || (/^\d+$/.test(value.trim()) && Number(value) >= 1 && Number(value) <= 366) ? undefined : t.daysInvalid,
    note: (value) => (value.trim().length >= 5 ? undefined : t.noteInvalid),
  });

  useEffect(() => {
    if (plans) return;
    api<{ plans: Array<{ code: string; days: number }> }>(`/admin/users/${userId}/subscriptions`).then((result) => {
      if (!result.ok) return;
      setPlans(result.data.plans);
      setPlan(result.data.plans[0]?.code ?? "");
    });
  }, [plans, userId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(false);
    const element = event.currentTarget;
    if (!validate(element)) return;
    const form = new FormData(element);
    const chosen = String(form.get("days")).trim();
    setPending(true);
    setFailure(null);
    const result = await api<AccessUpdate>(`/admin/users/${userId}/subscriptions`, {
      body: { plan, days: chosen ? Number(chosen) : null, note: String(form.get("note")).trim() },
    });
    setPending(false);
    if (!result.ok) return setFailure(result);
    setSaved(true);
    element.reset();
    onDone(result.data);
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4 rounded-xl border border-line bg-card p-4 sm:p-5">
      <div>
        <h3 className="text-h3 font-medium">{t.grantTitle}</h3>
        <p className="mt-1 text-small text-muted">{t.grantBody}</p>
      </div>
      {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
      {saved && <Alert tone="success">{t.granted}</Alert>}
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-label font-medium">{t.plan}</legend>
        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
          {plans?.map((option) => (
            <label
              key={option.code}
              className="flex min-h-12 cursor-pointer items-center gap-3 rounded-lg border border-line bg-card px-3 has-checked:border-accent has-checked:bg-accent-soft"
            >
              <input
                type="radio"
                name="plan"
                value={option.code}
                checked={plan === option.code}
                onChange={() => setPlan(option.code)}
                className="size-4 accent-accent"
              />
              <span className="min-w-0">
                <span className="block text-label font-medium">{planName(messages, option.code)}</span>
                <span className="block text-small text-muted">{interpolate(t.days, { days: option.days })}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <Field
        label={t.length}
        icon={CalendarDays}
        placeholder={interpolate(t.lengthPlaceholder, { days })}
        hint={t.lengthHint}
        inputMode="numeric"
        autoComplete="off"
        maxLength={3}
        {...field("days")}
        aria-required={false}
      />
      <Field
        label={t.note}
        icon={NotebookPen}
        placeholder={t.notePlaceholder}
        hint={t.noteHint}
        autoComplete="off"
        maxLength={300}
        enterKeyHint="send"
        {...field("note")}
      />
      <Button type="submit" variant="accent" size="lg" pending={pending} className="w-full sm:w-auto sm:self-start">
        {pending ? t.granting : t.grant}
      </Button>
    </form>
  );
}
