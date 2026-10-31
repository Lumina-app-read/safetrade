"use client";

import { KeyRound, Mail, MailCheck, ShieldCheck, TriangleAlert, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { PasswordField } from "@/components/ui/password-field";
import type { Locale } from "@/i18n/config";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { useFormErrors } from "@/lib/use-form-errors";
import { emailRule, newPasswordRule } from "@/lib/validation";

import { PasswordRules } from "./password-rules";

type ApiErr = { code: string; retryAfter?: number };

const primaryLink =
  "inline-flex h-12 w-full items-center justify-center rounded-lg bg-accent text-label font-medium text-on-accent hover:bg-accent-hover";
const secondaryLink =
  "inline-flex h-12 w-full items-center justify-center rounded-lg border border-line bg-card text-label font-medium hover:bg-page";

function Panel({ icon: Icon, tone, title, body, children }: { icon: LucideIcon; tone: string; title: string; body: string; children: ReactNode }) {
  return (
    <div className="flex animate-rise flex-col items-start gap-5" role="status">
      <span className={`grid size-14 place-items-center rounded-2xl ${tone}`}>
        <Icon size={28} strokeWidth={1.5} aria-hidden />
      </span>
      <div>
        <h1 className="text-h1">{title}</h1>
        <p className="mt-2 text-muted">{body}</p>
      </div>
      {children}
    </div>
  );
}

export function ForgotPasswordForm({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.auth.forgot;
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiErr | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const { field, validate } = useFormErrors({ email: emailRule(messages.auth.validation) });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validate(event.currentTarget)) return;
    const email = String(new FormData(event.currentTarget).get("email")).trim();
    setPending(true);
    setError(null);
    const result = await api("/auth/password/forgot", { body: { email } });
    setPending(false);
    if (result.ok) setSentTo(email);
    else setError(result);
  }

  if (sentTo) {
    return (
      <Panel icon={MailCheck} tone="bg-gain-soft text-gain" title={t.successTitle} body={interpolate(t.successBody, { email: sentTo })}>
        <Link href={`/${locale}/login`} className={secondaryLink}>
          {t.back}
        </Link>
      </Panel>
    );
  }
  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      <div>
        <h1 className="text-h1">{t.title}</h1>
        <p className="mt-1.5 text-muted">{t.subtitle}</p>
      </div>
      {error && <Alert tone="error">{errorMessage(messages, error)}</Alert>}
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
        enterKeyHint="send"
      />
      <Button type="submit" variant="accent" size="lg" pending={pending} className="w-full">
        {pending ? t.submitting : t.submit}
      </Button>
      <Link href={`/${locale}/login`} className="text-center font-medium text-accent-text underline-offset-4 hover:underline">
        {t.back}
      </Link>
    </form>
  );
}

export function ResetPasswordForm({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.auth.reset;
  const token = useSearchParams().get("token");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiErr | null>(null);
  const [done, setDone] = useState(false);
  const { errors, field, validate, setError: setFieldError } = useFormErrors({
    password: newPasswordRule(messages.auth.validation),
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validate(event.currentTarget)) return;
    setPending(true);
    setError(null);
    const result = await api("/auth/password/reset", { body: { token, password } });
    setPending(false);
    if (result.ok) setDone(true);
    else if (result.code.startsWith("auth.password")) setFieldError("password", errorMessage(messages, result));
    else setError(result);
  }

  if (!token) {
    return (
      <Panel icon={TriangleAlert} tone="bg-warn-soft text-warn" title={t.missingTitle} body={t.missingBody}>
        <Link href={`/${locale}/forgot-password`} className={secondaryLink}>
          {t.requestNew}
        </Link>
      </Panel>
    );
  }
  if (done) {
    return (
      <Panel icon={ShieldCheck} tone="bg-gain-soft text-gain" title={t.successTitle} body={t.successBody}>
        <Link href={`/${locale}/login`} className={primaryLink}>
          {t.goLogin}
        </Link>
      </Panel>
    );
  }
  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      <span className="grid size-14 place-items-center rounded-2xl bg-accent-soft text-accent-text">
        <KeyRound size={28} strokeWidth={1.5} aria-hidden />
      </span>
      <div>
        <h1 className="text-h1">{t.title}</h1>
        <p className="mt-1.5 text-muted">{t.subtitle}</p>
      </div>
      {error && (
        <Alert tone="error">
          {errorMessage(messages, error)}
          {error.code === "auth.reset_invalid" && (
            <Link href={`/${locale}/forgot-password`} className="mt-1 block font-medium text-accent-text underline underline-offset-4">
              {t.requestNew}
            </Link>
          )}
        </Alert>
      )}
      <PasswordField
        label={t.password}
        placeholder={t.passwordPlaceholder}
        {...field("password")}
        autoComplete="new-password"
        enterKeyHint="go"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        showLabel={messages.auth.showPassword}
        hideLabel={messages.auth.hidePassword}
        hint={<PasswordRules password={password} labels={messages.auth.register} invalid={Boolean(errors.password)} />}
      />
      <Button type="submit" variant="accent" size="lg" pending={pending} className="w-full">
        {pending ? t.submitting : t.submit}
      </Button>
    </form>
  );
}
