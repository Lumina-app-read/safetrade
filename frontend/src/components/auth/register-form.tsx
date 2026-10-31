"use client";

import { ArrowRight, Gift, Mail, MailCheck, UserRound } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { CodeInput } from "@/components/ui/code-input";
import { Field } from "@/components/ui/field";
import { PasswordField } from "@/components/ui/password-field";
import type { Locale } from "@/i18n/config";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { useFormErrors } from "@/lib/use-form-errors";
import { emailRule, newPasswordRule, requiredRule } from "@/lib/validation";

import { DerivSignup } from "../deriv-signup";
import { GoogleButton } from "./google-button";
import { PasswordRules } from "./password-rules";
import { ResendVerification } from "./resend-verification";

/** Formulaire ouvert depuis un lien de parrainage : le serveur revalide le code à l'envoi. */
export function ReferredRegisterForm({ locale, messages }: { locale: Locale; messages: Messages }) {
  const referral = useSearchParams().get("ref")?.slice(0, 16);
  return <RegisterForm key={referral} locale={locale} messages={messages} referral={referral} />;
}

export function RegisterForm({ locale, messages, referral }: { locale: Locale; messages: Messages; referral?: string }) {
  const t = messages.auth.register;
  const [password, setPassword] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [riskError, setRiskError] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<{ code: string; retryAfter?: number } | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [showCode, setShowCode] = useState(Boolean(referral));
  const v = messages.auth.validation;
  const { errors, field, validate, change, setError: setFieldError } = useFormErrors({
    first_name: requiredRule(v.firstNameRequired),
    email: emailRule(v),
    password: newPasswordRule(v),
    referral_code: (value) => (!value.trim() || /^[A-Za-z0-9]{8}$/.test(value.trim()) ? undefined : v.referralInvalid),
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fieldsOk = validate(event.currentTarget);
    setRiskError(!accepted);
    if (!fieldsOk || !accepted) return;
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email")).trim();
    setPending(true);
    setError(null);
    const result = await api("/auth/register", {
      body: {
        first_name: String(form.get("first_name")).trim(),
        email,
        password,
        locale,
        accept_risk: accepted,
        referral_code: String(form.get("referral_code") ?? "").trim() || null,
      },
    });
    setPending(false);
    if (result.ok) setSentTo(email);
    // Mot de passe refusé par le serveur : l'erreur s'affiche sous le champ concerné.
    else if (result.code.startsWith("auth.password")) setFieldError("password", errorMessage(messages, result));
    else if (result.code === "affiliate.unknown_code") setFieldError("referral_code", errorMessage(messages, result));
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
        <ResendVerification email={sentTo} messages={messages} />
        <div className="w-full empty:hidden">
          <DerivSignup messages={messages} />
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
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      <div>
        <h1 className="text-h1">{t.title}</h1>
        <p className="mt-1.5 text-muted">{t.subtitle}</p>
      </div>
      {error && <Alert tone="error">{errorMessage(messages, error)}</Alert>}
      <Field
        label={t.firstName}
        icon={UserRound}
        placeholder={t.firstNamePlaceholder}
        {...field("first_name")}
        maxLength={100}
        autoComplete="given-name"
        autoCapitalize="words"
        enterKeyHint="next"
      />
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
        autoComplete="new-password"
        enterKeyHint="go"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        showLabel={messages.auth.showPassword}
        hideLabel={messages.auth.hidePassword}
        hint={<PasswordRules password={password} labels={t} invalid={Boolean(errors.password)} />}
      />
      {showCode ? (
        <CodeInput
          name="referral_code"
          label={t.referralCode}
          boxLabel={messages.auth.codeBox}
          length={8}
          kind="letters"
          defaultValue={referral}
          error={errors.referral_code}
          onValueChange={(value) => change("referral_code", value)}
        />
      ) : (
        <button
          type="button"
          onClick={() => setShowCode(true)}
          className="flex min-h-11 items-center gap-2 self-start text-label font-medium text-accent-text underline-offset-4 hover:underline"
        >
          <Gift size={16} strokeWidth={1.5} aria-hidden />
          {t.referralToggle}
        </button>
      )}
      <Checkbox
        label={t.consent}
        checked={accepted}
        onChange={(e) => {
          setAccepted(e.target.checked);
          setRiskError(!e.target.checked);
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
