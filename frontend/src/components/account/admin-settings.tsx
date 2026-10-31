"use client";

import { Link2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { useAdmin } from "@/components/shell/admin-shell";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, SectionTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import type { Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { useFormErrors } from "@/lib/use-form-errors";

import { usePolled } from "../trading/use-live";

type Site = { deriv_signup_url: string | null };

function LinkForm({ current, messages }: { current: string | null; messages: Messages }) {
  const t = messages.adminSettings;
  const [pending, setPending] = useState(false);
  const [saved, setSaved] = useState(false);
  const [failure, setFailure] = useState<{ code: string; retryAfter?: number } | null>(null);
  const { field, validate, setError } = useFormErrors({
    deriv_signup_url: (value) => (!value.trim() || /^https:\/\/\S+$/.test(value.trim()) ? undefined : t.urlInvalid),
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(false);
    if (!validate(event.currentTarget)) return;
    const url = String(new FormData(event.currentTarget).get("deriv_signup_url")).trim();
    setPending(true);
    setFailure(null);
    const result = await api("/admin/site", { method: "PUT", body: { deriv_signup_url: url || null } });
    setPending(false);
    if (result.ok) setSaved(true);
    else if (result.code === "admin.invalid_url") setError("deriv_signup_url", t.urlInvalid);
    else setFailure(result);
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
      {saved && <Alert tone="success">{t.saved}</Alert>}
      <Field
        label={t.url}
        icon={Link2}
        placeholder={t.urlPlaceholder}
        hint={t.urlHint}
        defaultValue={current ?? ""}
        inputMode="url"
        autoComplete="off"
        spellCheck={false}
        autoCapitalize="none"
        maxLength={500}
        {...field("deriv_signup_url")}
        aria-required={false}
      />
      <Button type="submit" variant="primary" size="lg" pending={pending} className="w-full sm:w-auto sm:self-start">
        {pending ? t.saving : t.save}
      </Button>
    </form>
  );
}

/** Réglages du site. Le backend revérifie la permission et valide le lien. */
export function AdminSettings({ messages }: { messages: Messages }) {
  const t = messages.adminSettings;
  const { permissions } = useAdmin();
  const allowed = permissions.includes("settings.write");
  const site = usePolled<Site>(allowed ? "/admin/site" : null, 0);

  return (
    <>
      <h1 className="text-h1">{messages.admin.settings}</h1>
      <p className="mt-1 text-muted">{t.subtitle}</p>
      {!allowed && (
        <div className="mt-6">
          <Alert tone="error">{messages.admin.deniedBody}</Alert>
        </div>
      )}
      {allowed && (
        <>
          <SectionTitle>{t.partner}</SectionTitle>
          <Card className="p-5 sm:p-6">
            <p className="mb-4 max-w-2xl text-muted">{t.partnerBody}</p>
            {site.data ? (
              <LinkForm current={site.data.deriv_signup_url} messages={messages} />
            ) : site.error ? (
              <Alert tone="error">{errorMessage(messages, site.error)}</Alert>
            ) : (
              <p className="text-muted">{messages.trading.loading}</p>
            )}
          </Card>
        </>
      )}
    </>
  );
}
