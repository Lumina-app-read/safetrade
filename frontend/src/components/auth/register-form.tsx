"use client";

import { ArrowRight, Mail, MailCheck, UserRound } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import { PasswordField } from "@/components/ui/password-field";
import type { Locale } from "@/i18n/config";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";

import { GoogleButton } from "./google-button";
import { PasswordRules } from "./password-rules";

export function RegisterForm({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.auth.register;
  const [password, setPassword] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [riskError, setRiskError] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<{ code: string; retryAfter?: number } | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!accepted) return setRiskError(true);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email")).trim();
    setPending(true);
    setError(null);
    const result = await api("/auth/register", {
      body: { first_name: String(form.get("first_name")).trim(), email, password, locale, accept_risk: accepted },
    });
    setPending(false);
    if (result.ok) setSentTo(email);
    else setError(result);
  }

  if (sentTo) {
    return (
      <div className="flex animate-rise flex-col items-start gap-5" role="status">
        <span className="grid size-14 place-items-center rounded-2xl bg-gain-soft text-gain">
          <MailCheck size={28} strokeWidth={1.5} aria-hidden />
        </span>
        <div>
          <h1 className="text-h1">{t.successTitle}</h1>
          <p className="mt-2 text-muted">{interpolate(t.successBody, { email: sentTo })}</p>
        </div>
        <a
          href={`/${locale}/login`}
          className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-lg border border-line bg-card text-label font-medium hover:bg-page"
        >
          {t.backToLogin}
        </a>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5">
      <div>
        <h1 className="text-h1">{t.title}</h1>
        <p className="mt-1.5 text-muted">{t.subtitle}</p>
      </div>
      {error && <Alert tone="error">{errorMessage(messages, error)}</Alert>}
      <Field
        label={t.firstName}
        icon={UserRound}
        placeholder={t.firstNamePlaceholder}
        name="first_name"
        required
        maxLength={100}
        autoComplete="given-name"
        autoCapitalize="words"
        enterKeyHint="next"
      />
      <Field
        label={t.email}
        icon={Mail}
        placeholder={t.emailPlaceholder}
        name="email"
        type="email"
        required
        autoComplete="email"
        inputMode="email"
        autoCapitalize="none"
        spellCheck={false}
        enterKeyHint="next"
      />
      <PasswordField
        label={t.password}
        placeholder={t.passwordPlaceholder}
        name="password"
        required
        minLength={10}
        maxLength={128}
        autoComplete="new-password"
        enterKeyHint="go"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        showLabel={messages.auth.showPassword}
        hideLabel={messages.auth.hidePassword}
        hint={<PasswordRules password={password} labels={t} />}
      />
      <Checkbox
        label={t.consent}
        checked={accepted}
        onChange={(e) => {
          setAccepted(e.target.checked);
          setRiskError(false);
        }}
        error={riskError ? t.consentRequired : undefined}
      />
      <Button type="submit" variant="accent" size="lg" pending={pending} className="w-full">
        {pending ? t.submitting : t.submit}
        {!pending && <ArrowRight size={18} strokeWidth={1.5} aria-hidden />}
      </Button>
      <GoogleButton messages={messages} />
      <p className="text-center text-muted">
        {t.haveAccount}{" "}
        <a href={`/${locale}/login`} className="font-medium text-accent-text underline-offset-4 hover:underline">
          {t.signIn}
        </a>
      </p>
    </form>
  );
}
