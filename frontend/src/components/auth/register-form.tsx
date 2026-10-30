"use client";

import { ArrowRight, Check, Circle, MailCheck } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { PasswordField } from "@/components/ui/password-field";
import type { Locale } from "@/i18n/config";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";

// Règles affichées en direct ; le serveur reste seul juge (mêmes seuils côté backend).
const RULES = [
  { key: "ruleLength", test: (p: string) => p.length >= 10 },
  { key: "ruleVariety", test: (p: string) => new Set(p).size >= 4 },
] as const;

export function RegisterForm({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.auth.register;
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<{ code: string; retryAfter?: number } | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email")).trim();
    setPending(true);
    setError(null);
    const result = await api("/auth/register", {
      body: { first_name: String(form.get("first_name")).trim(), email, password, locale },
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
        name="first_name"
        required
        maxLength={100}
        autoComplete="given-name"
        autoCapitalize="words"
        enterKeyHint="next"
      />
      <Field
        label={t.email}
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
        hint={
          <ul className="mt-0.5 flex flex-col gap-1">
            {RULES.map(({ key, test }) => {
              const ok = test(password);
              const Icon = ok ? Check : Circle;
              return (
                <li key={key} className={cn("flex items-center gap-2 transition-colors", ok && "text-gain")}>
                  <Icon size={14} strokeWidth={ok ? 2 : 1.5} aria-hidden />
                  {t[key]}
                </li>
              );
            })}
          </ul>
        }
      />
      <p className="text-small text-muted">{t.consent}</p>
      <Button type="submit" variant="accent" size="lg" pending={pending} className="w-full">
        {pending ? t.submitting : t.submit}
        {!pending && <ArrowRight size={18} strokeWidth={1.5} aria-hidden />}
      </Button>
      <p className="text-center text-muted">
        {t.haveAccount}{" "}
        <a href={`/${locale}/login`} className="font-medium text-accent-text underline-offset-4 hover:underline">
          {t.signIn}
        </a>
      </p>
    </form>
  );
}
