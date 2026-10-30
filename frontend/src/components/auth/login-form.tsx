"use client";

import { ArrowRight, Mail } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { PasswordField } from "@/components/ui/password-field";
import type { Locale } from "@/i18n/config";
import type { Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";

export function LoginForm({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.auth.login;
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<{ code: string; retryAfter?: number } | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    const result = await api("/auth/login", {
      body: { email: String(form.get("email")), password: String(form.get("password")) },
    });
    if (result.ok) {
      // L'état reste « en attente » jusqu'à l'affichage du tableau de bord.
      router.replace(`/${locale}/dashboard`);
      return;
    }
    setPending(false);
    setError(result);
  }

  return (
    <form onSubmit={submit} noValidate={false} className="flex flex-col gap-5">
      <div>
        <h1 className="text-h1">{t.title}</h1>
        <p className="mt-1.5 text-muted">{t.subtitle}</p>
      </div>
      {error && <Alert tone={error.code === "auth.email_not_verified" ? "info" : "error"}>{errorMessage(messages, error)}</Alert>}
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
        autoComplete="current-password"
        enterKeyHint="go"
        showLabel={messages.auth.showPassword}
        hideLabel={messages.auth.hidePassword}
      />
      <Button type="submit" variant="accent" size="lg" pending={pending} className="mt-1 w-full">
        {pending ? t.submitting : t.submit}
        {!pending && <ArrowRight size={18} strokeWidth={1.5} aria-hidden />}
      </Button>
      <p className="text-center text-muted">
        {t.noAccount}{" "}
        <a href={`/${locale}/register`} className="font-medium text-accent-text underline-offset-4 hover:underline">
          {t.createAccount}
        </a>
      </p>
    </form>
  );
}
