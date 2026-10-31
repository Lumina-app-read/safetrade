"use client";

import { FlaskConical, KeyRound, Link2, Lock, Unlink } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { PasswordField } from "@/components/ui/password-field";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import type { Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useFormErrors } from "@/lib/use-form-errors";
import { requiredRule } from "@/lib/validation";

import { DerivSignup } from "../deriv-signup";
import type { DerivConnection } from "./types";

type Failure = { code: string; retryAfter?: number };

/** Le jeton part une fois vers le backend, qui le chiffre et ne le renvoie jamais. */
function ConnectForm({ messages, onDone, invalid }: { messages: Messages; onDone: () => void; invalid: boolean }) {
  const t = messages.trading.deriv;
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [opened, setOpened] = useState(false);
  const { field, validate } = useFormErrors({ token: requiredRule(t.tokenRequired) });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validate(event.currentTarget)) return;
    const form = event.currentTarget;
    const token = String(new FormData(form).get("token")).trim();
    setPending(true);
    setFailure(null);
    const result = await api("/deriv/connect", { body: { token } });
    setPending(false);
    if (result.ok) {
      form.reset();
      onDone();
    } else setFailure(result);
  }

  // Le champ n'apparaît qu'à la demande : pas de saisie de jeton sans action du client.
  if (!opened) {
    return (
      <div className="flex flex-col gap-3">
        {invalid && <Alert tone="error">{t.tokenExpired}</Alert>}
        <p className="text-muted">{t.intro}</p>
        <Button variant="accent" size="lg" className="w-full" onClick={() => setOpened(true)}>
          <Link2 size={18} strokeWidth={1.5} aria-hidden />
          {t.open}
        </Button>
        <DerivSignup messages={messages} variant="inline" />
      </div>
    );
  }

  return (
    <form onSubmit={submit} noValidate className="flex animate-rise flex-col gap-3">
      {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
      <PasswordField
        autoFocus
        label={t.token}
        placeholder={t.tokenPlaceholder}
        {...field("token")}
        icon={KeyRound}
        autoComplete="off"
        spellCheck={false}
        autoCapitalize="none"
        enterKeyHint="go"
        showLabel={messages.auth.showPassword}
        hideLabel={messages.auth.hidePassword}
      />
      <Button type="submit" variant="primary" size="lg" pending={pending} className="w-full">
        {!pending && <Link2 size={18} strokeWidth={1.5} aria-hidden />}
        {pending ? t.connecting : t.connect}
      </Button>
      <Button size="md" className="w-full" onClick={() => setOpened(false)}>
        {messages.trading.cancel}
      </Button>
      <p className="text-small text-muted">{t.scopes}</p>
    </form>
  );
}

/** Connexion Deriv et compte de travail. Le compte réel est visible, jamais sélectionnable. */
export function DerivPanel({
  connection,
  loading,
  botActive,
  locale,
  messages,
  onChanged,
}: {
  connection: DerivConnection | null;
  loading: boolean;
  botActive: boolean;
  locale: Locale;
  messages: Messages;
  onChanged: () => void;
}) {
  const t = messages.trading.deriv;
  const f = formatters(locale);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);

  async function disconnect() {
    setConfirm(false);
    setBusy(true);
    setFailure(null);
    const result = await api("/deriv/connection", { method: "DELETE" });
    setBusy(false);
    if (!result.ok) setFailure(result);
    onChanged();
  }

  const connected = connection?.connected === true;
  const valid = connected && connection.token_valid;

  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-h3 font-medium">
          <Link2 size={20} strokeWidth={1.5} aria-hidden className="text-muted" />
          {t.title}
        </h2>
        {!loading && <Badge tone={valid ? "gain" : "neutral"}>{valid ? t.connected : t.notConnected}</Badge>}
      </div>
      {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
      {loading && <p className="text-muted">{messages.trading.loading}</p>}
      {!loading && !valid && <ConnectForm messages={messages} onDone={onChanged} invalid={connected} />}
      {valid && (
        <>
          <ul className="flex flex-col gap-2">
            {connection.accounts.map((account) => {
              const selected = account.account_id === connection.selected.account_id;
              const locked = !account.selectable;
              return (
                <li
                  key={account.account_id}
                  className={cn(
                    "flex min-h-14 items-center justify-between gap-3 rounded-lg border p-3",
                    selected ? "border-accent" : "border-line",
                    locked && "bg-page",
                  )}
                >
                  <span className="flex min-w-0 items-center gap-2.5">
                    {locked ? (
                      <Lock size={18} strokeWidth={1.5} aria-hidden className="shrink-0 text-muted" />
                    ) : (
                      <FlaskConical size={18} strokeWidth={1.5} aria-hidden className="shrink-0 text-muted" />
                    )}
                    <span className="min-w-0">
                      <span className="block font-medium">{account.kind === "demo" ? t.demoAccount : t.realAccount}</span>
                      <span className="block truncate text-small text-muted">{locked ? t.realLocked : t.demoNote}</span>
                    </span>
                  </span>
                  {!locked && (
                    <span className="shrink-0 font-medium whitespace-nowrap tabular-nums">{f.money(Number(account.balance), account.currency)}</span>
                  )}
                </li>
              );
            })}
          </ul>
          <Button size="md" className="w-full" onClick={() => setConfirm(true)} disabled={botActive} pending={busy}>
            {!busy && <Unlink size={16} strokeWidth={1.5} aria-hidden />}
            {t.disconnect}
          </Button>
          {botActive && <p className="text-small text-muted">{t.disconnectBlocked}</p>}
        </>
      )}
      <Dialog open={confirm} onClose={() => setConfirm(false)} title={t.disconnectTitle} closeLabel={messages.trading.close}>
        <div className="flex flex-col gap-5">
          <p>{t.disconnectBody}</p>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button size="lg" onClick={() => setConfirm(false)}>
              {messages.trading.cancel}
            </Button>
            <Button size="lg" variant="danger" onClick={disconnect}>
              {t.disconnect}
            </Button>
          </div>
        </div>
      </Dialog>
    </Card>
  );
}
