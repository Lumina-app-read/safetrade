"use client";

import { Mail, RotateCw } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { useFormErrors } from "@/lib/use-form-errors";
import { emailRule } from "@/lib/validation";

const COOLDOWN_SECONDS = 60;

/**
 * Renvoi du lien de confirmation. Sans adresse connue, un champ la demande. La réponse du
 * serveur est la même que le compte existe ou non : le texte de confirmation reste neutre.
 */
export function ResendVerification({ email, messages }: { email?: string; messages: Messages }) {
  const t = messages.auth.resend;
  const { field, validate } = useFormErrors(email ? {} : { email: emailRule(messages.auth.validation) });
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<{ code: string; retryAfter?: number } | null>(null);
  const [wait, setWait] = useState(0);

  useEffect(() => {
    if (wait <= 0) return;
    const timer = setTimeout(() => setWait((value) => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [wait]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validate(event.currentTarget)) return;
    const address = email ?? String(new FormData(event.currentTarget).get("email")).trim();
    setPending(true);
    setError(null);
    const result = await api("/auth/verify-email/resend", { body: { email: address } });
    setPending(false);
    if (result.ok) {
      setSent(true);
      setWait(COOLDOWN_SECONDS);
    } else setError(result);
  }

  return (
    <form onSubmit={submit} noValidate className="flex w-full flex-col gap-3">
      {!email && (
        <Field
          label={messages.auth.register.email}
          icon={Mail}
          placeholder={messages.auth.register.emailPlaceholder}
          type="email"
          autoComplete="email"
          inputMode="email"
          autoCapitalize="none"
          spellCheck={false}
          enterKeyHint="send"
          {...field("email")}
        />
      )}
      {sent && <Alert tone="success">{t.sent}</Alert>}
      {error && <Alert tone="error">{errorMessage(messages, error)}</Alert>}
      <Button type="submit" variant="ghost" size="lg" pending={pending} disabled={wait > 0} className="w-full">
        {!pending && wait === 0 && <RotateCw size={16} strokeWidth={1.5} aria-hidden />}
        {pending ? t.sending : wait > 0 ? interpolate(t.wait, { seconds: wait }) : t.action}
      </Button>
      <p className="text-small text-muted">{t.hint}</p>
    </form>
  );
}
