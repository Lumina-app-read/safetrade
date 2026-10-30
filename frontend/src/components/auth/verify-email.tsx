"use client";

import { MailCheck, ShieldCheck, TriangleAlert } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { Locale } from "@/i18n/config";
import type { Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";

const linkClass =
  "inline-flex h-12 w-full items-center justify-center gap-2 rounded-lg text-label font-medium";

/**
 * Confirmation explicite par un bouton (requête POST) : les analyseurs de liens des
 * messageries, qui ouvrent les liens sans cliquer, ne consomment pas le jeton.
 */
export function VerifyEmail({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.auth.verify;
  const token = useSearchParams().get("token");
  const [state, setState] = useState<"idle" | "pending" | "done">("idle");
  const [error, setError] = useState<{ code: string } | null>(null);

  async function confirm() {
    setState("pending");
    setError(null);
    const result = await api("/auth/verify-email", { body: { token } });
    if (result.ok) setState("done");
    else {
      setState("idle");
      setError(result);
    }
  }

  const [Icon, title, body, tone] = !token
    ? [TriangleAlert, t.missingTitle, t.missingBody, "bg-warn-soft text-warn"]
    : state === "done"
      ? [MailCheck, t.successTitle, t.successBody, "bg-gain-soft text-gain"]
      : [ShieldCheck, t.title, t.body, "bg-accent-soft text-accent-text"];

  return (
    <div key={state} className="flex animate-rise flex-col items-start gap-5">
      <span className={`grid size-14 place-items-center rounded-2xl ${tone}`}>
        <Icon size={28} strokeWidth={1.5} aria-hidden />
      </span>
      <div>
        <h1 className="text-h1">{title}</h1>
        <p className="mt-2 text-muted">{body}</p>
      </div>
      {error && <Alert tone="error">{errorMessage(messages, error)}</Alert>}
      {!token ? (
        <a href={`/${locale}/register`} className={`${linkClass} border border-line bg-card hover:bg-page`}>
          {t.registerAgain}
        </a>
      ) : state === "done" ? (
        <a href={`/${locale}/login`} className={`${linkClass} bg-accent text-on-accent hover:bg-accent-hover`}>
          {t.goLogin}
        </a>
      ) : (
        <Button variant="accent" size="lg" className="w-full" pending={state === "pending"} onClick={confirm}>
          {state === "pending" ? t.submitting : t.submit}
        </Button>
      )}
    </div>
  );
}
