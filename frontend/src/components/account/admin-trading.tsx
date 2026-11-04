"use client";

import { Coins, Layers, ListX, NotebookPen, OctagonAlert, Play, Square } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { usePolled } from "@/components/trading/use-live";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, SectionTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { useFormErrors } from "@/lib/use-form-errors";

import { AdminTitle, ReasonAction, type ApiErr } from "./admin-ui";

type Controls = { halted: boolean; max_stake: string | null; max_positions: number | null; disabled_symbols: string[] };
type BotRow = {
  id: string;
  email: string;
  user_id: string;
  symbol: string;
  account_kind: string;
  state: string;
  command: string | null;
  error_code: string | null;
  heartbeat_at: string | null;
  started_at: string;
  open_positions: number;
};
type Data = { controls: Controls; bots: BotRow[] };

/**
 * Plafonds globaux, arrêt d'urgence et supervision des bots. Ces contrôles s'ajoutent au module
 * de risque de chaque client : ils ne peuvent que restreindre, et le moteur les relit à chaque tour.
 */
export function AdminTrading({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.adminTrading;
  const f = formatters(locale);
  const polled = usePolled<Data>("/admin/trading", 10000);
  const [override, setOverride] = useState<Data | null>(null);
  const data = override ?? polled.data;
  const [stopping, setStopping] = useState<string | null>(null);
  const [failure, setFailure] = useState<ApiErr | null>(null);

  async function stop(bot: BotRow) {
    setStopping(bot.id);
    setFailure(null);
    const result = await api<Pick<Data, "bots">>(`/admin/trading/bots/${bot.id}/stop`, { method: "POST" });
    setStopping(null);
    if (result.ok && data) setOverride({ ...data, bots: result.data.bots });
    else if (!result.ok) setFailure(result);
  }

  if (!data) {
    return (
      <>
        <AdminTitle title={messages.admin.risk} subtitle={t.subtitle} />
        <p className="mt-6 text-muted">{polled.error ? errorMessage(messages, polled.error) : messages.trading.loading}</p>
      </>
    );
  }
  const { controls } = data;

  return (
    <>
      <AdminTitle title={messages.admin.risk} subtitle={t.subtitle} />

      <Card className={`mt-6 p-5 sm:p-6 ${controls.halted ? "border-loss" : ""}`}>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <span className={`grid size-11 shrink-0 place-items-center rounded-xl ${controls.halted ? "bg-loss-soft text-loss" : "bg-gain-soft text-gain"}`}>
              <OctagonAlert size={22} strokeWidth={1.5} aria-hidden />
            </span>
            <div>
              <h2 className="text-h3 font-medium">{controls.halted ? t.haltedTitle : t.runningTitle}</h2>
              <p className="mt-1 max-w-xl text-small text-muted">{controls.halted ? t.haltedBody : t.runningBody}</p>
            </div>
          </div>
        </div>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
          {controls.halted ? (
            <ReasonAction
              messages={messages}
              label={t.resume}
              confirm={t.confirmResume}
              pending={t.working}
              icon={Play}
              variant="primary"
              onSubmit={(note) => api<Data>("/admin/trading/halt", { method: "PUT", body: { halted: false, note } })}
              onDone={setOverride}
            />
          ) : (
            <>
              <ReasonAction
                messages={messages}
                label={t.halt}
                confirm={t.confirmHalt}
                pending={t.working}
                icon={Square}
                variant="danger"
                onSubmit={(note) => api<Data>("/admin/trading/halt", { method: "PUT", body: { halted: true, note } })}
                onDone={setOverride}
              />
              <ReasonAction
                messages={messages}
                label={t.haltAndClose}
                confirm={t.confirmHaltAndClose}
                pending={t.working}
                icon={OctagonAlert}
                variant="danger"
                onSubmit={(note) =>
                  api<Data>("/admin/trading/halt", { method: "PUT", body: { halted: true, close_positions: true, note } })
                }
                onDone={setOverride}
              />
            </>
          )}
        </div>
      </Card>

      <SectionTitle>{t.limits}</SectionTitle>
      <LimitsForm key={JSON.stringify(controls)} controls={controls} messages={messages} onSaved={setOverride} />

      <SectionTitle>{interpolate(t.bots, { count: data.bots.length })}</SectionTitle>
      {failure && (
        <div className="mb-3">
          <Alert tone="error">{errorMessage(messages, failure)}</Alert>
        </div>
      )}
      <Card className="p-2 sm:p-3">
        {data.bots.length === 0 && <p className="p-3 text-muted">{t.noBots}</p>}
        <ul className="divide-y divide-line">
          {data.bots.map((bot) => (
            <li key={bot.id} className="flex flex-col gap-3 px-2 py-3 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{bot.symbol}</span>
                  <Badge tone={bot.error_code ? "loss" : "gain"}>{t.states[bot.state as keyof typeof t.states] ?? bot.state}</Badge>
                  <Badge tone="neutral">{bot.account_kind === "real" ? t.real : t.demo}</Badge>
                </div>
                <Link
                  href={`/${locale}/admin/users/sheet?id=${bot.user_id}`}
                  className="mt-1 block truncate text-small text-accent-text underline-offset-4 hover:underline"
                >
                  {bot.email}
                </Link>
                <p className="mt-0.5 text-small text-muted">
                  {[
                    interpolate(t.since, { date: f.relative(bot.started_at) }),
                    bot.heartbeat_at ? interpolate(t.heartbeat, { date: f.relative(bot.heartbeat_at) }) : t.noHeartbeat,
                    interpolate(t.positions, { count: bot.open_positions }),
                  ].join(" · ")}
                </p>
              </div>
              {bot.command === "stop" || bot.command === "emergency" || bot.state === "stopping" ? (
                <Badge tone="warn">{t.stopRequested}</Badge>
              ) : (
                <Button type="button" variant="danger" pending={stopping === bot.id} onClick={() => stop(bot)} className="self-start sm:self-center">
                  <Square size={16} strokeWidth={1.5} aria-hidden />
                  {t.stop}
                </Button>
              )}
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}

function LimitsForm({ controls, messages, onSaved }: { controls: Controls; messages: Messages; onSaved: (data: Data) => void }) {
  const t = messages.adminTrading;
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ApiErr | null>(null);
  const [saved, setSaved] = useState(false);
  const { field, validate } = useFormErrors({
    max_stake: (value) =>
      !value.trim() || (/^\d{1,2}([.,]\d{1,2})?$/.test(value.trim()) && Number(value.replace(",", ".")) >= 1 && Number(value.replace(",", ".")) <= 50)
        ? undefined
        : t.stakeInvalid,
    max_positions: (value) => (!value.trim() || /^[1-3]$/.test(value.trim()) ? undefined : t.positionsInvalid),
    note: (value) => (value.trim().length >= 5 ? undefined : messages.adminUi.noteInvalid),
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(false);
    if (!validate(event.currentTarget)) return;
    const form = new FormData(event.currentTarget);
    const stake = String(form.get("max_stake")).trim().replace(",", ".");
    const positions = String(form.get("max_positions")).trim();
    const symbols = String(form.get("disabled_symbols"))
      .split(/[\s,;]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    setPending(true);
    setFailure(null);
    const result = await api<Data>("/admin/trading/controls", {
      method: "PUT",
      body: {
        max_stake: stake || null,
        max_positions: positions ? Number(positions) : null,
        disabled_symbols: symbols,
        note: String(form.get("note")).trim(),
      },
    });
    setPending(false);
    if (!result.ok) return setFailure(result);
    setSaved(true);
    onSaved(result.data);
  }

  return (
    <Card className="p-5 sm:p-6">
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <p className="max-w-2xl text-small text-muted">{t.limitsBody}</p>
        {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
        {saved && <Alert tone="success">{t.saved}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label={t.maxStake}
            icon={Coins}
            placeholder={t.noLimit}
            hint={t.maxStakeHint}
            defaultValue={controls.max_stake ?? ""}
            inputMode="decimal"
            autoComplete="off"
            maxLength={5}
            {...field("max_stake")}
            aria-required={false}
          />
          <Field
            label={t.maxPositions}
            icon={Layers}
            placeholder={t.noLimit}
            hint={t.maxPositionsHint}
            defaultValue={controls.max_positions?.toString() ?? ""}
            inputMode="numeric"
            autoComplete="off"
            maxLength={1}
            {...field("max_positions")}
            aria-required={false}
          />
        </div>
        <Field
          label={t.disabled}
          icon={ListX}
          placeholder={t.disabledPlaceholder}
          hint={t.disabledHint}
          defaultValue={controls.disabled_symbols.join(", ")}
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          name="disabled_symbols"
        />
        <Field
          label={messages.adminUi.note}
          icon={NotebookPen}
          placeholder={messages.adminUi.notePlaceholder}
          autoComplete="off"
          maxLength={300}
          {...field("note")}
        />
        <Button type="submit" variant="primary" size="lg" pending={pending} className="w-full sm:w-auto sm:self-start">
          {pending ? t.saving : t.save}
        </Button>
      </form>
    </Card>
  );
}

