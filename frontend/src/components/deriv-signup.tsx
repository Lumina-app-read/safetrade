"use client";

import { ExternalLink, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/card";
import type { Messages } from "@/i18n/messages";
import { api } from "@/lib/api";

let config: Promise<string | null> | null = null;

function readSignupUrl(): Promise<string | null> {
  config ??= api<{ deriv_signup_url: string | null }>("/site/config").then((result) => (result.ok ? result.data.deriv_signup_url : null));
  return config;
}

function useSignupUrl(): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    void readSignupUrl().then((value) => {
      if (active) setUrl(value);
    });
    return () => {
      active = false;
    };
  }, []);
  return url;
}

/**
 * Invitation à ouvrir un compte Deriv, par le lien partenaire défini dans l'administration.
 * Aucun lien enregistré : rien n'est affiché.
 */
export function DerivSignup({ messages, variant = "card" }: { messages: Messages; variant?: "card" | "inline" }) {
  const t = messages.derivSignup;
  const url = useSignupUrl();
  if (!url) return null;
  const link = (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer sponsored"
      className="inline-flex min-h-11 items-center gap-1.5 text-label font-medium text-accent-text underline-offset-4 hover:underline"
    >
      {t.action}
      <ExternalLink size={16} strokeWidth={1.5} aria-hidden />
    </a>
  );

  if (variant === "inline") {
    return (
      <div className="flex flex-col border-t border-line pt-3">
        <p className="font-medium">{t.title}</p>
        {link}
        <p className="text-small text-muted">{t.disclosure}</p>
      </div>
    );
  }
  return (
    <Card className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:gap-4">
      <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-text">
        <UserPlus size={20} strokeWidth={1.5} aria-hidden />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-h3 font-medium">{t.title}</span>
        <span className="mt-0.5 block text-muted">{t.body}</span>
        <span className="mt-1 block text-small text-muted">{t.disclosure}</span>
      </span>
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer sponsored"
        className="inline-flex h-12 shrink-0 items-center justify-center gap-2 rounded-lg bg-accent px-5 text-label font-medium text-on-accent transition-colors hover:bg-accent-hover"
      >
        {t.action}
        <ExternalLink size={18} strokeWidth={1.5} aria-hidden />
      </a>
    </Card>
  );
}
