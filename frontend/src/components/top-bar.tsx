"use client";

import { ChartLine, CreditCard, History, LayoutDashboard, Menu, ShieldCheck, type LucideIcon } from "lucide-react";
import { useState } from "react";

import { LanguageSwitch } from "@/components/language-switch";
import { ThemeSwitch } from "@/components/theme-switch";
import type { Locale } from "@/i18n/config";
import type { Messages } from "@/i18n/messages";
import { cn } from "@/lib/cn";

const NAV: Array<{ key: keyof Omit<Messages["nav"], "menu">; icon: LucideIcon }> = [
  { key: "dashboard", icon: LayoutDashboard },
  { key: "trading", icon: ChartLine },
  { key: "history", icon: History },
  { key: "subscription", icon: CreditCard },
];

export function TopBar({ locale, messages, current }: { locale: Locale; messages: Messages; current?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-10 border-b border-line bg-card">
      <div className="mx-auto flex h-16 max-w-[1200px] items-center gap-4 px-4 sm:px-6">
        <button
          type="button"
          className="p-2 text-fg lg:hidden"
          aria-label={messages.nav.menu}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <Menu size={20} strokeWidth={1.5} aria-hidden />
        </button>
        <div className="flex items-center gap-2 text-h3 font-medium">
          <span className="grid size-8 place-items-center rounded-lg bg-accent text-on-accent">
            <ShieldCheck size={20} strokeWidth={1.5} aria-hidden />
          </span>
          <span className="max-sm:hidden">SafeTrade</span>
        </div>
        <nav
          className={cn(
            "mx-auto gap-1 lg:flex",
            open
              ? "absolute inset-x-0 top-16 flex flex-col border-b border-line bg-card px-4 pt-2 pb-4"
              : "hidden",
          )}
        >
          {NAV.map(({ key, icon: Icon }) => (
            <a
              key={key}
              href="#"
              aria-current={current === key ? "page" : undefined}
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-label font-medium text-muted hover:bg-page hover:text-fg aria-[current=page]:bg-accent-soft aria-[current=page]:text-accent-text"
            >
              <Icon size={20} strokeWidth={1.5} aria-hidden />
              {messages.nav[key]}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2 lg:ml-0">
          <ThemeSwitch labels={messages.theme} />
          <LanguageSwitch current={locale} label={messages.language.label} names={messages.language.names} />
          <span className="grid size-8 place-items-center rounded-full bg-accent-soft text-label font-medium text-accent-text">
            CM
          </span>
        </div>
      </div>
    </header>
  );
}
