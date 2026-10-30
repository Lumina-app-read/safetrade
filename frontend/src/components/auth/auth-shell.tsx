import { ChartLine, Lock, ShieldCheck, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Logo } from "@/components/brand/logo";
import { LanguageSwitch } from "@/components/language-switch";
import { ThemeSwitch } from "@/components/theme-switch";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import type { Messages } from "@/i18n/messages";

import { DemoSessionCard } from "./demo-chart";

/**
 * Ossature des pages de connexion et d'inscription.
 * Téléphone : page verticale pleine largeur, en-tête compact, formulaire intégré.
 * Ordinateur : panneau de marque à gauche, formulaire à droite.
 */
export function AuthShell({ locale, messages, children }: { locale: Locale; messages: Messages; children: ReactNode }) {
  const a = messages.auth;
  const points: Array<[LucideIcon, string]> = [
    [ShieldCheck, a.panelPoint1],
    [ChartLine, a.panelPoint2],
    [Lock, a.panelPoint3],
  ];
  return (
    <div className="min-h-dvh bg-card lg:grid lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <aside className="relative hidden overflow-hidden bg-anthracite text-on-anthracite lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-16">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-40 -left-32 size-[560px] rounded-full bg-[radial-gradient(circle,var(--brand-ring),transparent_65%)] blur-2xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -right-40 -bottom-48 size-[480px] rounded-full border-[56px] border-accent/15"
        />
        <a href={`/${locale}`} className="relative w-fit">
          <Logo onDark />
        </a>
        <div className="relative max-w-lg animate-rise">
          <p className="text-small tracking-[0.08em] text-on-anthracite/60 uppercase">{a.panelEyebrow}</p>
          <h2 className="mt-4 text-[32px] leading-tight xl:text-[38px]">{a.panelTitle}</h2>
          <ul className="mt-8 flex flex-col gap-4">
            {points.map(([Icon, text]) => (
              <li key={text} className="flex items-start gap-3 text-on-anthracite/85">
                <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-on-anthracite/10 bg-on-anthracite/5">
                  <Icon size={18} strokeWidth={1.5} aria-hidden />
                </span>
                <span className="pt-1.5">{text}</span>
              </li>
            ))}
          </ul>
          <div className="mt-10 max-w-sm">
            <DemoSessionCard messages={a} result={formatters(locale).money(3.84)} />
          </div>
        </div>
        <p className="relative text-small text-on-anthracite/55">{a.riskNote}</p>
      </aside>

      <main className="flex min-h-dvh flex-col">
        <header className="flex h-16 items-center justify-between gap-3 border-b border-line px-5 sm:px-8 lg:border-b-0">
          <a href={`/${locale}`} className="lg:invisible">
            <Logo />
          </a>
          <div className="flex items-center gap-2">
            <ThemeSwitch labels={messages.theme} />
            <LanguageSwitch current={locale} label={messages.language.label} names={messages.language.names} />
          </div>
        </header>
        <div className="flex flex-1 flex-col px-5 pt-8 pb-6 sm:px-8 lg:justify-center lg:pt-0">
          <div className="mx-auto w-full max-w-[420px] animate-rise">{children}</div>
        </div>
        <p className="px-5 pb-[max(env(safe-area-inset-bottom),20px)] text-center text-small text-muted sm:px-8 lg:hidden">
          {a.riskNote}
        </p>
      </main>
    </div>
  );
}
