"use client";

import {
  Check,
  Copy,
  Download,
  KeyRound,
  LaptopMinimal,
  LockKeyhole,
  LogOut,
  ShieldCheck,
  ShieldOff,
  Smartphone,
  Tablet,
} from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { useSession } from "@/components/shell/session";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { PasswordField } from "@/components/ui/password-field";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { describeDevice } from "@/lib/device";

type SessionRow = {
  id: string;
  created_at: string;
  last_seen_at: string;
  ip_address: string | null;
  user_agent: string | null;
  current: boolean;
};
type ApiErr = { code: string; retryAfter?: number };

export function SecurityPanel({ locale, messages }: { locale: Locale; messages: Messages }) {
  const { user, refresh } = useSession();
  const [sessions, setSessions] = useState<SessionRow[] | null>(null);

  const loadSessions = useCallback(async () => {
    const result = await api<{ sessions: SessionRow[] }>("/auth/sessions");
    if (result.ok) setSessions(result.data.sessions);
  }, []);

  useEffect(() => {
    let active = true;
    api<{ sessions: SessionRow[] }>("/auth/sessions").then((result) => {
      if (active && result.ok) setSessions(result.data.sessions);
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
      <MfaCard messages={messages} enabled={user.mfa_enabled} onChange={refresh} />
      <SessionsCard locale={locale} messages={messages} sessions={sessions} reload={loadSessions} />
    </div>
  );
}

function CardHeader({ icon: Icon, title, body, badge }: { icon: typeof ShieldCheck; title: string; body: string; badge?: React.ReactNode }) {
  return (
    <div className="flex items-start gap-4">
      <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-text">
        <Icon size={20} strokeWidth={1.5} aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h2 className="text-h3 font-medium">{title}</h2>
          {badge}
        </div>
        <p className="mt-1 text-muted">{body}</p>
      </div>
    </div>
  );
}

function useCopy() {
  const [copied, setCopied] = useState<string | null>(null);
  async function copy(key: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      setTimeout(() => setCopied((c) => (c === key ? null : c)), 2000);
    } catch {
      // Presse-papiers refusé : l'utilisateur peut toujours sélectionner le texte.
    }
  }
  return { copied, copy };
}

type Setup = { secret: string; qr_svg: string };

function MfaCard({ messages, enabled, onChange }: { messages: Messages; enabled: boolean; onChange: () => void }) {
  const t = messages.security;
  const [stage, setStage] = useState<"idle" | "setup" | "codes" | "disable">("idle");
  const [setup, setSetup] = useState<Setup | null>(null);
  const [codes, setCodes] = useState<string[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiErr | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { copied, copy } = useCopy();

  async function start() {
    setPending(true);
    setError(null);
    setNotice(null);
    const result = await api<Setup>("/auth/mfa/setup", { method: "POST" });
    setPending(false);
    if (!result.ok) return setError(result);
    setSetup(result.data);
    setStage("setup");
  }

  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const code = String(new FormData(event.currentTarget).get("code")).replace(/\s/g, "");
    setPending(true);
    setError(null);
    const result = await api<{ recovery_codes: string[] }>("/auth/mfa/enable", { body: { code } });
    setPending(false);
    if (!result.ok) return setError(result);
    setCodes(result.data.recovery_codes);
    setSetup(null);
    setStage("codes");
    onChange();
  }

  async function disable(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    const result = await api("/auth/mfa/disable", {
      body: { password: String(form.get("password")), code: String(form.get("code")).replace(/\s/g, "") },
    });
    setPending(false);
    if (!result.ok) return setError(result);
    setStage("idle");
    onChange();
    setNotice(t.disabledNotice);
  }

  function download() {
    const content = `${t.codesFile}\n${t.codesFileNote}\n\n${codes.join("\n")}\n`;
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
    const link = Object.assign(document.createElement("a"), { href: url, download: "safetrade-recovery-codes.txt" });
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Card className="flex flex-col gap-5 max-sm:-mx-5 max-sm:rounded-none max-sm:border-x-0 max-sm:px-5">
      <CardHeader
        icon={enabled ? ShieldCheck : LockKeyhole}
        title={t.mfaTitle}
        body={t.mfaBody}
        badge={<Badge tone={enabled ? "gain" : "neutral"}>{enabled ? t.mfaOn : t.mfaOff}</Badge>}
      />
      {error && <Alert tone="error">{errorMessage(messages, error)}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      {stage === "setup" && setup && (
        <form onSubmit={confirm} className="flex animate-rise flex-col gap-5">
          <ol className="flex flex-col gap-5">
            <li className="flex flex-col gap-3">
              <p className="flex gap-2.5">
                <StepNumber n={1} />
                {t.step1}
              </p>
              <div className="flex flex-col items-center gap-3 rounded-xl border border-line bg-page p-4 sm:flex-row sm:items-start">
                {/* SVG généré par notre backend (segno), affiché comme image : aucun script exécutable. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`data:image/svg+xml;utf8,${encodeURIComponent(setup.qr_svg)}`}
                  alt=""
                  width={176}
                  height={176}
                  className="size-44 shrink-0 rounded-lg"
                />
                <div className="flex w-full min-w-0 flex-col gap-2">
                  <span className="text-small text-muted">{t.manual}</span>
                  <code className="rounded-lg border border-line bg-card px-3 py-2.5 font-mono text-small break-all">
                    {setup.secret.match(/.{1,4}/g)?.join(" ")}
                  </code>
                  <Button
                    icon={copied === "secret" ? <Check size={16} strokeWidth={1.75} aria-hidden /> : <Copy size={16} strokeWidth={1.5} aria-hidden />}
                    onClick={() => copy("secret", setup.secret)}
                  >
                    {copied === "secret" ? t.copied : t.copy}
                  </Button>
                </div>
              </div>
            </li>
            <li className="flex flex-col gap-3">
              <p className="flex gap-2.5">
                <StepNumber n={2} />
                {t.step2}
              </p>
              <Field
                label={messages.auth.mfa.code}
                icon={Smartphone}
                name="code"
                required
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9 ]{6,7}"
                maxLength={7}
                placeholder={messages.auth.mfa.codePlaceholder}
                className="[&_input]:tracking-[0.3em] [&_input]:tabular-nums"
              />
            </li>
          </ol>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button size="lg" onClick={() => setStage("idle")}>
              {t.cancel}
            </Button>
            <Button type="submit" variant="accent" size="lg" pending={pending}>
              {pending ? t.confirming : t.confirm}
            </Button>
          </div>
        </form>
      )}

      {stage === "codes" && (
        <div className="flex animate-rise flex-col gap-4">
          <Alert tone="success">{t.enabledNotice}</Alert>
          <div>
            <h3 className="font-medium">{t.codesTitle}</h3>
            <p className="mt-1 text-small text-muted">{t.codesBody}</p>
          </div>
          <ul className="grid grid-cols-2 gap-2 rounded-xl border border-line bg-page p-3 font-mono text-body tabular-nums">
            {codes.map((c) => (
              <li key={c} className="rounded-md bg-card px-2 py-1.5 text-center">
                {c}
              </li>
            ))}
          </ul>
          <div className="grid grid-cols-2 gap-3">
            <Button
              size="lg"
              icon={copied === "codes" ? <Check size={16} strokeWidth={1.75} aria-hidden /> : <Copy size={16} strokeWidth={1.5} aria-hidden />}
              onClick={() => copy("codes", codes.join("\n"))}
            >
              {copied === "codes" ? t.copied : t.copyAll}
            </Button>
            <Button size="lg" icon={<Download size={16} strokeWidth={1.5} aria-hidden />} onClick={download}>
              {t.download}
            </Button>
          </div>
          <Button variant="primary" size="lg" onClick={() => setStage("idle")}>
            {t.codesSaved}
          </Button>
        </div>
      )}

      {stage === "disable" && (
        <form onSubmit={disable} className="flex animate-rise flex-col gap-4 rounded-xl border border-line p-4">
          <div>
            <h3 className="font-medium">{t.disableTitle}</h3>
            <p className="mt-1 text-small text-muted">{t.disableBody}</p>
          </div>
          <PasswordField
            label={t.password}
            name="password"
            required
            autoComplete="current-password"
            showLabel={messages.auth.showPassword}
            hideLabel={messages.auth.hidePassword}
          />
          <Field label={t.code} icon={KeyRound} name="code" required autoComplete="one-time-code" maxLength={9} />
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button size="lg" onClick={() => setStage("idle")}>
              {t.cancel}
            </Button>
            <Button type="submit" variant="danger" size="lg" pending={pending}>
              {pending ? t.disabling : t.disableConfirm}
            </Button>
          </div>
        </form>
      )}

      {stage === "idle" &&
        (enabled ? (
          <Button size="lg" icon={<ShieldOff size={18} strokeWidth={1.5} aria-hidden />} onClick={() => setStage("disable")} className="sm:self-start">
            {t.disable}
          </Button>
        ) : (
          <Button variant="accent" size="lg" pending={pending} icon={<ShieldCheck size={18} strokeWidth={1.5} aria-hidden />} onClick={start} className="sm:self-start">
            {pending ? t.starting : t.enable}
          </Button>
        ))}
    </Card>
  );
}

function StepNumber({ n }: { n: number }) {
  return (
    <span className="grid size-6 shrink-0 place-items-center rounded-full bg-anthracite text-small font-medium text-on-anthracite">
      {n}
    </span>
  );
}

function SessionsCard({
  locale,
  messages,
  sessions,
  reload,
}: {
  locale: Locale;
  messages: Messages;
  sessions: SessionRow[] | null;
  reload: () => Promise<void>;
}) {
  const t = messages.security;
  const f = formatters(locale);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<ApiErr | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const others = sessions?.filter((s) => !s.current) ?? [];

  async function revoke(id: string) {
    setBusy(id);
    setError(null);
    setNotice(null);
    const result = await api(`/auth/sessions/${id}`, { method: "DELETE" });
    if (!result.ok) setError(result);
    await reload();
    setBusy(null);
  }

  async function revokeOthers() {
    setBusy("others");
    setError(null);
    const result = await api<{ revoked: number }>("/auth/sessions/revoke-others", { method: "POST" });
    if (result.ok) setNotice(interpolate(t.revokedNotice, { count: result.data.revoked }));
    else setError(result);
    await reload();
    setBusy(null);
  }

  return (
    <Card className="flex flex-col gap-5 max-sm:-mx-5 max-sm:rounded-none max-sm:border-x-0 max-sm:px-5">
      <CardHeader icon={LaptopMinimal} title={t.sessionsTitle} body={t.sessionsBody} />
      {error && <Alert tone="error">{errorMessage(messages, error)}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}
      {sessions === null ? (
        <p className="text-muted">{t.loading}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {sessions.map((s) => {
            const device = describeDevice(s.user_agent);
            const Icon = device.kind === "mobile" ? Smartphone : device.kind === "tablet" ? Tablet : LaptopMinimal;
            return (
              <li key={s.id} className="flex animate-fade items-center gap-3 rounded-xl border border-line p-3.5 sm:p-4">
                <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-page text-muted">
                  <Icon size={20} strokeWidth={1.5} aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="truncate font-medium">{device.label ?? t.unknownDevice}</span>
                    {s.current && <Badge tone="gain">{t.thisDevice}</Badge>}
                  </div>
                  <p className="text-small text-muted">
                    {s.ip_address ?? t.ipUnknown} · {interpolate(t.lastActive, { time: f.relative(s.last_seen_at) })}
                  </p>
                  <p className="text-small text-muted">{interpolate(t.since, { date: f.date(s.created_at) })}</p>
                </div>
                {!s.current && (
                  <Button
                    variant="danger"
                    pending={busy === s.id}
                    onClick={() => revoke(s.id)}
                    aria-label={`${t.revoke} : ${device.label ?? t.unknownDevice}`}
                    className="shrink-0 max-sm:size-10 max-sm:px-0"
                    icon={<LogOut size={16} strokeWidth={1.5} aria-hidden />}
                  >
                    <span className="max-sm:sr-only">{t.revoke}</span>
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {sessions !== null &&
        (others.length > 0 ? (
          <Button size="lg" pending={busy === "others"} onClick={revokeOthers} icon={<LogOut size={18} strokeWidth={1.5} aria-hidden />} className="sm:self-start">
            {t.revokeOthers}
          </Button>
        ) : (
          <p className="text-small text-muted">{t.noOther}</p>
        ))}
    </Card>
  );
}
