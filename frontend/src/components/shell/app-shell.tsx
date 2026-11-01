"use client";

import { ChartLine, CreditCard, Gift, History, LayoutDashboard, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { Logo } from "@/components/brand/logo";
import { LanguageSelect } from "@/components/language-select";
import { ThemeToggle } from "@/components/theme-toggle";
import type { Locale } from "@/i18n/config";
import type { Messages } from "@/i18n/messages";

import { SessionGate } from "./session";
import { UserMenu } from "./user-menu";

type NavItem = { path: string; label: keyof Messages["nav"]; short?: keyof Messages["nav"]; icon: LucideIcon };

const NAV: NavItem[] = [
  { path: "/dashboard", label: "dashboard", short: "home", icon: LayoutDashboard },
  { path: "/trading", label: "trading", icon: ChartLine },
  { path: "/history", label: "history", icon: History },
  { path: "/subscription", label: "subscription", short: "plan", icon: CreditCard },
  { path: "/affiliate", label: "affiliate", icon: Gift },
];

/**
 * Coquille de l'espace client. Téléphone : barre compacte en haut et onglets en bas,
 * à portée de pouce. Ordinateur : navigation dans la barre du haut.
 */
export function AppShell({ locale, messages, children }: { locale: Locale; messages: Messages; children: ReactNode }) {
  const pathname = usePathname();
  const isCurrent = (path: string) => pathname === `/${locale}${path}`;
  // Le tableau de trading profite de toute la largeur d'un grand écran.
  const width = isCurrent("/trading") ? "max-w-[1560px]" : "max-w-[1200px]";

  return (
    <SessionGate locale={locale} messages={messages}>
      <div className="min-h-dvh bg-page">
        <header className="sticky top-0 z-20 border-b border-line bg-card/90 backdrop-blur-xl">
          <div className={`mx-auto flex h-16 ${width} items-center gap-2 px-4 sm:gap-3 sm:px-6`}>
            <Link href={`/${locale}/dashboard`} aria-label={messages.nav.dashboard}>
              <Logo compact />
            </Link>
            <nav aria-label={messages.nav.primary} className="mx-auto hidden items-center gap-1 lg:flex">
              {NAV.map(({ path, label, icon: Icon }) => (
                <Link
                  key={path}
                  href={`/${locale}${path}`}
                  aria-current={isCurrent(path) ? "page" : undefined}
                  className="flex items-center gap-2 rounded-lg px-3 py-2 text-label font-medium text-muted transition-colors hover:text-fg aria-[current=page]:bg-accent-soft aria-[current=page]:text-accent-text"
                >
                  <Icon size={18} strokeWidth={1.5} aria-hidden />
                  {messages.nav[label]}
                </Link>
              ))}
            </nav>
            <div className="ml-auto flex items-center gap-2 lg:ml-0">
              <ThemeToggle labels={messages.theme} />
              <LanguageSelect current={locale} labels={messages.language} />
              <UserMenu locale={locale} messages={messages} area="app" />
            </div>
          </div>
        </header>

        {/* Marge basse sur téléphone : les onglets fixes ne masquent jamais le contenu. */}
        <main
          key={pathname}
          className={`mx-auto ${width} animate-rise px-4 pt-5 pb-[calc(88px+env(safe-area-inset-bottom))] sm:px-6 sm:pt-8 lg:pb-16`}
        >
          {children}
        </main>

        <nav
          aria-label={messages.nav.primary}
          className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 border-t border-line bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"
        >
          {NAV.map(({ path, label, short, icon: Icon }) => (
            <Link
              key={path}
              href={`/${locale}${path}`}
              aria-current={isCurrent(path) ? "page" : undefined}
              className="relative flex min-h-16 min-w-0 flex-col items-center justify-center gap-1 text-small text-muted transition-colors aria-[current=page]:font-medium aria-[current=page]:text-accent-text"
            >
              {isCurrent(path) && <span aria-hidden className="absolute inset-x-4 top-0 h-0.5 rounded-b bg-accent" />}
              <Icon size={20} strokeWidth={1.5} aria-hidden />
              <span className="max-w-full truncate px-0.5">{messages.nav[short ?? label]}</span>
            </Link>
          ))}
        </nav>
      </div>
    </SessionGate>
  );
}
