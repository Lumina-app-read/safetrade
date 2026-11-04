"use client";

import { ArrowLeft, FileText } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { api } from "@/lib/api";

export type LegalKind = "legal_notice" | "terms" | "privacy" | "risk";
type Document = { title: string; body: string; version: number; locale: string; published_at: string };

/**
 * Texte en clair : un titre par ligne commençant par « # », une liste par lignes « - »,
 * des paragraphes séparés par une ligne vide. Jamais de HTML : rien n'est interprété.
 */
function blocks(body: string): ReactNode[] {
  return body.split(/\n\s*\n/).map((chunk, index) => {
    const lines = chunk.split("\n").map((line) => line.trim()).filter(Boolean);
    if (lines.length === 1 && lines[0].startsWith("#")) {
      return (
        <h2 key={index} className="mt-8 text-h2">
          {lines[0].replace(/^#+\s*/, "")}
        </h2>
      );
    }
    if (lines.every((line) => line.startsWith("- "))) {
      return (
        <ul key={index} className="mt-4 flex list-disc flex-col gap-2 pl-5">
          {lines.map((line, item) => (
            <li key={item}>{line.slice(2)}</li>
          ))}
        </ul>
      );
    }
    return (
      <p key={index} className="mt-4 leading-relaxed">
        {lines.join(" ")}
      </p>
    );
  });
}

export function LegalPage({ kind, locale, messages }: { kind: LegalKind; locale: Locale; messages: Messages }) {
  const t = messages.legalPage;
  const f = formatters(locale);
  const [document, setDocument] = useState<Document | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    let active = true;
    api<Document>(`/site/legal?kind=${kind}&locale=${locale}`).then((result) => {
      if (!active) return;
      if (result.ok) setDocument(result.data);
      else setMissing(true);
    });
    return () => {
      active = false;
    };
  }, [kind, locale]);

  return (
    <main className="mx-auto w-full max-w-[760px] px-5 pt-10 pb-20 sm:px-6 sm:pt-14">
      <a href={`/${locale}`} className="inline-flex min-h-11 items-center gap-1.5 text-label text-muted hover:text-fg">
        <ArrowLeft size={16} strokeWidth={1.5} aria-hidden />
        {t.back}
      </a>
      <div className="mt-4 flex items-center gap-3">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-text">
          <FileText size={20} strokeWidth={1.5} aria-hidden />
        </span>
        <h1 className="text-h1">{document?.title ?? t.titles[kind]}</h1>
      </div>
      {document && (
        <p className="mt-3 text-small text-muted">
          {interpolate(t.version, { version: document.version, date: f.date(document.published_at) })}
          {document.locale !== locale && ` · ${t.otherLanguage}`}
        </p>
      )}
      {missing && <p className="mt-6 text-muted">{t.notPublished}</p>}
      {!document && !missing && <p className="mt-6 text-muted">{t.loading}</p>}
      {document && <article className="mt-4 break-words">{blocks(document.body)}</article>}
    </main>
  );
}
