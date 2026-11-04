"use client";

import { CalendarDays, ChevronRight, NotebookPen, Search, ShieldOff } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { useAdmin } from "@/components/shell/admin-shell";
import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useFormErrors } from "@/lib/use-form-errors";

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
type Detail = {
  user: { id: string; email: string; first_name: string };
  access: Access;
  history: Period[];
  plans: Array<{ code: string; days: number }>;
};
type ApiErr = { code: string; retryAfter?: number };

const TONE: Record<Access["status"], BadgeTone> = {
  active: "gain",
  trial: "brand",
  expired: "warn",
  suspended: "loss",
  none: "neutral",
};

function planName(messages: Messages, code: string): string {
  return messages.plans.levels[code as keyof Messages["plans"]["levels"]] ?? code;
}

/** Comptes et accès. Le serveur revérifie chaque permission et calcule seul l'accès. */
export function AdminUsers({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.adminUsers;
  const [query, setQuery] = useState("");
  const [users, setUsers] = useState<UserRow[] | null>(null);
  const [error, setError] = useState<ApiErr | null>(null);
  const [selected, setSelected] = useState<UserRow | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      const search = query.trim() ? `&q=${encodeURIComponent(query.trim())}` : "";
      api<{ users: UserRow[] }>(`/admin/users?limit=100${search}`).then((result) => {
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
  }, [query, version]);

  return (
    <>
      <h1 className="text-h1">{messages.admin.users}</h1>
      <p className="mt-1 text-muted">{t.subtitle}</p>

      <div className="mt-6">
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
              <button
                type="button"
                onClick={() => setSelected(user)}
                className="flex min-h-16 w-full items-center gap-3 rounded-lg px-2 py-2.5 text-left hover:bg-page"
              >
                <span className="grid size-10 shrink-0 place-items-center rounded-full bg-page text-label font-medium uppercase">
                  {user.first_name.slice(0, 1)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{user.first_name}</span>
                  <span className="block truncate text-small text-muted">{user.email}</span>
                </span>
                <AccessBadge access={user.access} messages={messages} />
                <ChevronRight size={16} strokeWidth={1.5} aria-hidden className="shrink-0 text-muted" />
              </button>
            </li>
          ))}
        </ul>
      </Card>

      <Dialog
        open={selected !== null}
        onClose={() => {
          setSelected(null);
          setVersion((value) => value + 1);
        }}
        title={selected ? selected.first_name : t.subtitle}
        closeLabel={messages.trading.close}
      >
        {selected && <UserAccess key={selected.id} userId={selected.id} locale={locale} messages={messages} />}
      </Dialog>
    </>
  );
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

function UserAccess({ userId, locale, messages }: { userId: string; locale: Locale; messages: Messages }) {
  const t = messages.adminUsers;
  const f = formatters(locale);
  const { permissions } = useAdmin();
  const canGrant = permissions.includes("subscriptions.write");
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<ApiErr | null>(null);

  useEffect(() => {
    let active = true;
    api<Detail>(`/admin/users/${userId}/subscriptions`).then((result) => {
      if (!active) return;
      if (result.ok) setDetail(result.data);
      else setError(result);
    });
    return () => {
      active = false;
    };
  }, [userId]);

  if (error) return <Alert tone="error">{errorMessage(messages, error)}</Alert>;
  if (!detail) return <p className="text-muted">{messages.trading.loading}</p>;

  const update = (next: Pick<Detail, "access" | "history">) => setDetail({ ...detail, ...next });
  const last = detail.history.find((period) => !period.revoked_at);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="truncate text-small text-muted">{detail.user.email}</p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <AccessBadge access={detail.access} messages={messages} />
          <span className="text-muted">
            {detail.access.ends_at
              ? interpolate(t.until, { date: f.dateTime(detail.access.ends_at) })
              : t.noAccess}
          </span>
        </div>
      </div>

      {canGrant ? (
        <GrantForm userId={userId} plans={detail.plans} messages={messages} onDone={update} />
      ) : (
        <Alert tone="info">{t.readOnly}</Alert>
      )}

      <section>
        <h3 className="text-h3 font-medium">{t.history}</h3>
        {detail.history.length === 0 && <p className="mt-2 text-muted">{t.noHistory}</p>}
        <ul className="mt-3 flex flex-col gap-3">
          {detail.history.map((period) => (
            <li
              key={period.id}
              className={cn("rounded-xl border border-line p-4", period.revoked_at && "opacity-70")}
            >
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
                <RevokeForm userId={userId} periodId={period.id} messages={messages} onDone={update} />
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function GrantForm({
  userId,
  plans,
  messages,
  onDone,
}: {
  userId: string;
  plans: Detail["plans"];
  messages: Messages;
  onDone: (next: Pick<Detail, "access" | "history">) => void;
}) {
  const t = messages.adminUsers;
  const [plan, setPlan] = useState(plans[0]?.code ?? "");
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ApiErr | null>(null);
  const [saved, setSaved] = useState(false);
  const days = plans.find((p) => p.code === plan)?.days ?? 7;
  const { field, validate } = useFormErrors({
    days: (value) => (!value.trim() || (/^\d+$/.test(value.trim()) && Number(value) >= 1 && Number(value) <= 366) ? undefined : t.daysInvalid),
    note: (value) => (value.trim().length >= 5 ? undefined : t.noteInvalid),
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(false);
    if (!validate(event.currentTarget)) return;
    const form = new FormData(event.currentTarget);
    const chosen = String(form.get("days")).trim();
    setPending(true);
    setFailure(null);
    const result = await api<Pick<Detail, "access" | "history">>(`/admin/users/${userId}/subscriptions`, {
      body: { plan, days: chosen ? Number(chosen) : null, note: String(form.get("note")).trim() },
    });
    setPending(false);
    if (!result.ok) return setFailure(result);
    setSaved(true);
    onDone(result.data);
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4 rounded-xl border border-line bg-page p-4 sm:p-5">
      <div>
        <h3 className="text-h3 font-medium">{t.grantTitle}</h3>
        <p className="mt-1 text-small text-muted">{t.grantBody}</p>
      </div>
      {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
      {saved && <Alert tone="success">{t.granted}</Alert>}
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-label font-medium">{t.plan}</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {plans.map((option) => (
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

function RevokeForm({
  userId,
  periodId,
  messages,
  onDone,
}: {
  userId: string;
  periodId: string;
  messages: Messages;
  onDone: (next: Pick<Detail, "access" | "history">) => void;
}) {
  const t = messages.adminUsers;
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ApiErr | null>(null);
  const { field, validate } = useFormErrors({
    note: (value) => (value.trim().length >= 5 ? undefined : t.noteInvalid),
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validate(event.currentTarget)) return;
    const note = String(new FormData(event.currentTarget).get("note")).trim();
    setPending(true);
    setFailure(null);
    const result = await api<Pick<Detail, "access" | "history">>(
      `/admin/users/${userId}/subscriptions/${periodId}/revoke`,
      { body: { note } },
    );
    setPending(false);
    if (!result.ok) return setFailure(result);
    onDone(result.data);
  }

  if (!open) {
    return (
      <Button type="button" variant="danger" className="mt-3" onClick={() => setOpen(true)}>
        <ShieldOff size={16} strokeWidth={1.5} aria-hidden />
        {t.revoke}
      </Button>
    );
  }
  return (
    <form onSubmit={submit} noValidate className="mt-3 flex flex-col gap-3">
      {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
      <Field
        label={t.revokeNote}
        icon={NotebookPen}
        placeholder={t.notePlaceholder}
        autoComplete="off"
        maxLength={300}
        autoFocus
        {...field("note")}
      />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="danger" pending={pending}>
          {pending ? t.revoking : t.confirmRevoke}
        </Button>
        <Button type="button" onClick={() => setOpen(false)}>
          {messages.trading.cancel}
        </Button>
      </div>
    </form>
  );
}
