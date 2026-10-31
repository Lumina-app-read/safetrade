"use client";

import { ArrowLeft, ArrowRight, KeyRound, Mail, ShieldCheck, Smartphone } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { PasswordField } from "@/components/ui/password-field";
import type { Locale } from "@/i18n/config";
import type { Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { homePath } from "@/lib/roles";
import { useFormErrors } from "@/lib/use-form-errors";
import { currentPasswordRule, emailRule, recoveryRule, totpRule } from "@/lib/validation";

import { GoogleButton } from "./google-button";
import { ResendVerification } from "./resend-verification";

type LoginResult = { user?: { role: string }; mfa_required?: boolean; challenge?: string };
type ApiErr = { code: string; retryAfter?: number };

const linkButton = "inline-flex items-center gap-1.5 font-medium text-accent-text underline-offset-4 hover:underline";

export function LoginForm({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.auth.login;
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiErr | null>(null);
  const [challenge, setChallenge] = useState<string | null>(null);
  const [unverified, setUnverified] = useState<string | null>(null);
  const v = messages.auth.validation;
  const { field, validate } = useFormErrors({ email: emailRule(v), password: currentPasswordRule(v) });

  function done(role: string | undefined) {
    // L'état reste « en attente » jusqu'à l'affichage de la page d'arrivée.
    router.replace(homePath(locale, role));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validate(event.currentTarget)) return;
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email")).trim();
    setPending(true);
    setError(null);
    setUnverified(null);
    const result = await api<LoginResult>("/auth/login", {
      body: {
        email,
        password: String(form.get("password")),
        remember: form.get("remember") === "on",
      },
    });
    if (result.ok && result.data.mfa_required && result.data.challenge) {
      setPending(false);
      setChallenge(result.data.challenge);
      return;
    }
    if (result.ok) return done(result.data.user?.role);
    setPending(false);
    setError(result);
    if (result.code === "auth.email_not_verified") setUnverified(email);
  }

  if (challenge) {
    return (
      <MfaStep
        messages={messages}
        challenge={challenge}
        onSuccess={done}
        onRestart={() => {
          setChallenge(null);
          setError(null);
        }}
      />
    );
  }

  return (
    <div className="flex flex-col gap-5">
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      <div>
        <h1 className="text-h1">{t.title}</h1>
        <p className="mt-1.5 text-muted">{t.subtitle}</p>
      </div>
      {error && (
        <Alert tone={error.code === "auth.email_not_verified" ? "info" : "error"}>{errorMessage(messages, error)}</Alert>
      )}
      <Field
        label={t.email}
        icon={Mail}
        placeholder={t.emailPlaceholder}
        {...field("email")}
        type="email"
        autoComplete="email"
        inputMode="email"
        autoCapitalize="none"
        spellCheck={false}
        enterKeyHint="next"
      />
      <PasswordField
        label={t.password}
        placeholder={t.passwordPlaceholder}
        {...field("password")}
        autoComplete="current-password"
        enterKeyHint="go"
        showLabel={messages.auth.showPassword}
        hideLabel={messages.auth.hidePassword}
      />
      <div className="-my-1 flex flex-wrap items-center justify-between gap-x-4">
        <Checkbox name="remember" label={t.remember} />
        <Link href={`/${locale}/forgot-password`} className={`${linkButton} min-h-11 text-label`}>
          {t.forgot}
        </Link>
      </div>
      <Button type="submit" variant="accent" size="lg" pending={pending} className="mt-1 w-full">
        {pending ? t.submitting : t.submit}
        {!pending && <ArrowRight size={18} strokeWidth={1.5} aria-hidden />}
      </Button>
      <GoogleButton messages={messages} />
      <p className="text-center text-muted">
        {t.noAccount}{" "}
        <a href={`/${locale}/register`} className={linkButton}>
          {t.createAccount}
        </a>
      </p>
    </form>
    {unverified && <ResendVerification email={unverified} messages={messages} />}
    </div>
  );
}

/** Second temps de la connexion : code de l'application ou code de secours. */
function MfaStep({
  messages,
  challenge,
  onSuccess,
  onRestart,
}: {
  messages: Messages;
  challenge: string;
  onSuccess: (role: string | undefined) => void;
  onRestart: () => void;
}) {
  const t = messages.auth.mfa;
  const [recovery, setRecovery] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiErr | null>(null);
  const v = messages.auth.validation;
  const { field, validate } = useFormErrors({ code: recovery ? recoveryRule(v) : totpRule(v) });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validate(event.currentTarget)) return;
    const code = String(new FormData(event.currentTarget).get("code")).replace(/\s/g, "");
    setPending(true);
    setError(null);
    const result = await api<LoginResult>("/auth/login/mfa", { body: { challenge, code } });
    if (result.ok) return onSuccess(result.data.user?.role);
    setPending(false);
    setError(result);
  }

  return (
    <form key={recovery ? "recovery" : "app"} onSubmit={submit} noValidate className="flex animate-rise flex-col gap-5">
      <span className="grid size-14 place-items-center rounded-2xl bg-accent-soft text-accent-text">
        <ShieldCheck size={28} strokeWidth={1.5} aria-hidden />
      </span>
      <div>
        <h1 className="text-h1">{t.title}</h1>
        <p className="mt-1.5 text-muted">{t.subtitle}</p>
      </div>
      {error && <Alert tone="error">{errorMessage(messages, error)}</Alert>}
      {recovery ? (
        <Field
          label={t.recoveryCode}
          icon={KeyRound}
          {...field("code")}
          autoFocus
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          maxLength={9}
          placeholder={t.recoveryPlaceholder}
          enterKeyHint="go"
        />
      ) : (
        <Field
          label={t.code}
          icon={Smartphone}
          {...field("code")}
          autoFocus
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={7}
          placeholder={t.codePlaceholder}
          enterKeyHint="go"
          className="[&_input]:tracking-[0.3em] [&_input]:tabular-nums"
        />
      )}
      <Button type="submit" variant="accent" size="lg" pending={pending} className="w-full">
        {pending ? t.submitting : t.submit}
      </Button>
      <div className="flex flex-col items-center gap-3 text-small">
        <button type="button" className={linkButton} onClick={() => setRecovery((v) => !v)}>
          {recovery ? t.useApp : t.useRecovery}
        </button>
        <button type="button" className="inline-flex items-center gap-1.5 text-muted hover:text-fg" onClick={onRestart}>
          <ArrowLeft size={16} strokeWidth={1.5} aria-hidden />
          {t.back}
        </button>
      </div>
    </form>
  );
}
