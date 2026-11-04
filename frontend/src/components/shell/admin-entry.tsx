"use client";

import { ArrowLeft, Clock, KeyRound, LockKeyhole, MailCheck, ShieldCheck, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Logo } from "@/components/brand/logo";
import { LanguageSelect } from "@/components/language-select";
import { ThemeToggle } from "@/components/theme-toggle";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { CodeInput } from "@/components/ui/code-input";
import { PasswordField } from "@/components/ui/password-field";
import type { Locale } from "@/i18n/config";
import type { Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { useFormErrors } from "@/lib/use-form-errors";
import { currentPasswordRule, totpRule } from "@/lib/validation";

type ApiErr = { code: string; retryAfter?: number };

/**
 * Seconde connexion de l'administration, sur une session client déjà ouverte. Le serveur
 * vérifie le rôle, le mot de passe et un code frais ; il ferme la session après trois échecs.
 */
export function AdminEntry({ locale, messages, onEntered }: { locale: Locale; messages: Messages; onEntered: () => void }) {
  const t = messages.adminEntry;
  const v = messages.auth.validation;
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiErr | null>(null);
  const [attempt, setAttempt] = useState(0);
  const { field, validate, change } = useFormErrors({ password: currentPasswordRule(v), code: totpRule(v) });

  const steps: Array<[LucideIcon, string]> = [
    [ShieldCheck, t.step1],
    [LockKeyhole, t.step2],
    [KeyRound, t.step3],
    [Clock, t.step4],
    [MailCheck, t.step5],
  ];

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validate(event.currentTarget)) return;
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    const result = await api("/auth/admin/enter", {
      body: { password: String(form.get("password")), code: String(form.get("code")).replace(/\s/g, "") },
    });
    if (result.ok) return onEntered();
    // Session fermée par le serveur après trop d'échecs : retour à la connexion.
    if (result.code === "admin.locked" || result.status === 401 && result.code === "auth.not_authenticated") {
      window.location.replace(`/${locale}/login`);
      return;
    }
    setPending(false);
    setError(result);
    setAttempt((value) => value + 1);
  }

  return (
    <div className="min-h-dvh bg-card lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <aside className="relative hidden overflow-hidden bg-anthracite text-on-anthracite lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-16">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-40 -left-32 size-[520px] rounded-full bg-[radial-gradient(circle,var(--brand-ring),transparent_65%)] blur-2xl"
        />
        <span className="relative w-fit">
          <Logo onDark />
        </span>
        <div className="relative max-w-lg animate-rise">
          <p className="text-small tracking-[0.08em] text-on-anthracite/60 uppercase">{t.eyebrow}</p>
          <h2 className="mt-4 text-[32px] leading-tight xl:text-[38px]">{t.panelTitle}</h2>
          <ol className="mt-8 flex flex-col gap-4">
            {steps.map(([Icon, text]) => (
              <li key={text} className="flex items-start gap-3 text-on-anthracite/85">
                <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-on-anthracite/10 bg-on-anthracite/5">
                  <Icon size={18} strokeWidth={1.5} aria-hidden />
                </span>
                <span className="pt-1.5">{text}</span>
              </li>
            ))}
          </ol>
        </div>
        <p className="relative text-small text-on-anthracite/55">{t.panelNote}</p>
      </aside>

      <main className="flex min-h-dvh flex-col">
        <header className="flex h-16 items-center justify-between gap-3 border-b border-line px-5 sm:px-8 lg:border-b-0">
          <span className="lg:invisible">
            <Logo />
          </span>
          <div className="flex items-center gap-2">
            <ThemeToggle labels={messages.theme} />
            <LanguageSelect current={locale} labels={messages.language} />
          </div>
        </header>
        <div className="flex flex-1 flex-col px-5 pt-8 pb-8 sm:px-8 lg:justify-center lg:pt-0">
          <form
            key={attempt}
            onSubmit={submit}
            noValidate
            className="mx-auto flex w-full max-w-[420px] animate-rise flex-col gap-5"
          >
            <span className="grid size-14 place-items-center rounded-2xl bg-accent-soft text-accent-text">
              <ShieldCheck size={28} strokeWidth={1.5} aria-hidden />
            </span>
            <div>
              <h1 className="text-h1">{t.title}</h1>
              <p className="mt-1.5 text-muted">{t.subtitle}</p>
            </div>
            {error && <Alert tone="error">{errorMessage(messages, error)}</Alert>}
            <PasswordField
              label={t.password}
              placeholder={messages.auth.login.passwordPlaceholder}
              {...field("password")}
              autoComplete="current-password"
              enterKeyHint="next"
              autoFocus
              showLabel={messages.auth.showPassword}
              hideLabel={messages.auth.hidePassword}
            />
            <CodeInput
              name="code"
              label={t.code}
              boxLabel={messages.auth.codeBox}
              error={field("code").error}
              onValueChange={(value) => change("code", value)}
            />
            <p className="-mt-2 text-small text-muted">{t.codeHint}</p>
            <Button type="submit" variant="primary" size="lg" pending={pending} className="w-full">
              {pending ? t.submitting : t.submit}
            </Button>
            {/* Téléphone : les contrôles du panneau restent visibles, en résumé. */}
            <ul className="flex flex-col gap-2.5 rounded-xl border border-line bg-page p-4 text-small text-muted lg:hidden">
              {steps.map(([Icon, text]) => (
                <li key={text} className="flex items-start gap-2.5">
                  <Icon size={16} strokeWidth={1.5} aria-hidden className="mt-0.5 shrink-0" />
                  {text}
                </li>
              ))}
            </ul>
            <Link
              href={`/${locale}/dashboard`}
              className="inline-flex min-h-11 items-center justify-center gap-1.5 text-label text-muted hover:text-fg"
            >
              <ArrowLeft size={16} strokeWidth={1.5} aria-hidden />
              {t.back}
            </Link>
          </form>
        </div>
      </main>
    </div>
  );
}
