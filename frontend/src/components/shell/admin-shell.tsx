"use client";

import {
  Coins,
  CreditCard,
  Gauge,
  LayoutDashboard,
  ScrollText,
  Settings,
  ShieldAlert,
  ShieldCheck,
  UserCog,
  Users,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { Logo } from "@/components/brand/logo";
import { LanguageSelect } from "@/components/language-select";
import { ThemeToggle } from "@/components/theme-toggle";
import type { Locale } from "@/i18n/config";
import type { Messages } from "@/i18n/messages";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";

import { SessionGate } from "./session";
import { UserMenu } from "./user-menu";

export type AdminProfile = {
  user: { id: string; email: string; first_name: string; role: string };
  permissions: string[];
};

const AdminContext = createContext<AdminProfile | null>(null);

export function useAdmin(): AdminProfile {
  const admin = useContext(AdminContext);
  if (!admin) throw new Error("useAdmin doit être utilisé sous AdminShell");
  return admin;
}

type ModuleKey = keyof Pick<
  Messages["admin"],
  "overview" | "users" | "subscriptions" | "payments" | "affiliates" | "risk" | "settings" | "team" | "audit"
>;

// Modules de la section 10, construits en phase 5. `path` : module déjà disponible.
const MODULES: Array<{ key: ModuleKey; icon: LucideIcon; permission?: string; path?: string }> = [
  { key: "overview", icon: LayoutDashboard, path: "" },
  { key: "users", icon: Users, permission: "users.read" },
  { key: "subscriptions", icon: CreditCard, permission: "settings.write" },
  { key: "payments", icon: Coins, permission: "payments.read" },
  { key: "affiliates", icon: UserCog, permission: "affiliates.read", path: "/affiliates" },
  { key: "risk", icon: Gauge, permission: "risk.write" },
  { key: "settings", icon: Settings, permission: "settings.write" },
  { key: "team", icon: ShieldCheck, permission: "team.write" },
  { key: "audit", icon: ScrollText, permission: "audit.read" },
];

/**
 * Coquille de l'administration, séparée de l'espace client. Le contenu ne s'affiche
 * qu'après la réponse de GET /admin/me : c'est le backend qui accorde ou refuse l'accès.
 */
export function AdminShell({ locale, messages, children }: { locale: Locale; messages: Messages; children: ReactNode }) {
  return (
    <SessionGate locale={locale} messages={messages}>
      <AdminGate locale={locale} messages={messages}>
        {children}
      </AdminGate>
    </SessionGate>
  );
}

function AdminGate({ locale, messages, children }: { locale: Locale; messages: Messages; children: ReactNode }) {
  const t = messages.admin;
  const [admin, setAdmin] = useState<AdminProfile | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const pathname = usePathname();

  useEffect(() => {
    let active = true;
    api<AdminProfile>("/admin/me").then((result) => {
      if (!active) return;
      if (result.ok) setAdmin(result.data);
      else setRefusal(result.code);
    });
    return () => {
      active = false;
    };
  }, []);

  if (refusal) {
    const mfa = refusal === "authz.mfa_required";
    return (
      <div className="flex min-h-dvh flex-col bg-card">
        <header className="flex h-16 items-center px-5 sm:px-8">
          <Logo />
        </header>
        <main className="mx-auto flex w-full max-w-md flex-1 animate-rise flex-col justify-center gap-5 px-5 pb-16">
          <span className="grid size-14 place-items-center rounded-2xl bg-accent-soft text-accent-text">
            <ShieldAlert size={28} strokeWidth={1.5} aria-hidden />
          </span>
          <div>
            <h1 className="text-h1">{mfa ? t.mfaTitle : t.deniedTitle}</h1>
            <p className="mt-2 text-muted">{mfa ? t.mfaBody : t.deniedBody}</p>
          </div>
          <Link
            href={`/${locale}/${mfa ? "account/security" : "dashboard"}`}
            className="inline-flex h-12 items-center justify-center rounded-lg bg-accent px-5 text-label font-medium text-on-accent hover:bg-accent-hover"
          >
            {mfa ? t.mfaAction : t.deniedAction}
          </Link>
        </main>
      </div>
    );
  }
  if (!admin) {
    return (
      <p role="status" className="grid min-h-dvh animate-fade place-items-center px-5 text-muted">
        {messages.shell.loading}
      </p>
    );
  }

  const modules = MODULES.filter((m) => !m.permission || admin.permissions.includes(m.permission));
  const item = "flex shrink-0 items-center gap-2.5 rounded-lg text-label font-medium";

  return (
    <AdminContext.Provider value={admin}>
      <div className="min-h-dvh bg-page lg:grid lg:grid-cols-[256px_minmax(0,1fr)]">
        <aside className="sticky top-0 hidden h-dvh flex-col gap-6 overflow-y-auto bg-anthracite p-4 text-on-anthracite lg:flex">
          <div className="px-2 pt-2">
            <Logo onDark />
            <p className="mt-2 text-small tracking-[0.08em] text-on-anthracite/60 uppercase">{t.brand}</p>
          </div>
          <nav aria-label={t.navLabel} className="flex flex-col gap-1">
            {modules.map(({ key, icon: Icon, path }) =>
              path !== undefined ? (
                <Link
                  key={key}
                  href={`/${locale}/admin${path}`}
                  aria-current={pathname === `/${locale}/admin${path}` ? "page" : undefined}
                  className={cn(item, "px-3 py-2.5 text-on-anthracite hover:bg-on-anthracite/10 aria-[current=page]:bg-accent aria-[current=page]:text-on-accent")}
                >
                  <Icon size={18} strokeWidth={1.5} aria-hidden />
                  {t[key]}
                </Link>
              ) : (
                <span key={key} aria-disabled className={cn(item, "px-3 py-2.5 text-on-anthracite/60")}>
                  <Icon size={18} strokeWidth={1.5} aria-hidden />
                  <span className="flex-1">{t[key]}</span>
                  <span className="text-[11px] font-normal">{t.soon}</span>
                </span>
              ),
            )}
          </nav>
        </aside>

        <div className="min-w-0">
          <header className="sticky top-0 z-20 border-b border-line bg-card/90 backdrop-blur-xl">
            <div className="flex h-16 items-center gap-3 px-5 sm:px-6">
              <span className="flex min-w-0 items-center gap-3 lg:hidden">
                <Logo compact />
                <span className="truncate text-label font-medium text-muted">{t.brand}</span>
              </span>
              <div className="ml-auto flex items-center gap-2">
                <ThemeToggle labels={messages.theme} />
                <LanguageSelect current={locale} labels={messages.language} />
                <UserMenu locale={locale} messages={messages} area="admin" />
              </div>
            </div>
            {/* Téléphone : modules en bandeau horizontal, sans menu caché. */}
            <nav
              aria-label={t.navLabel}
              className="flex gap-2 overflow-x-auto px-5 pb-3 [scrollbar-width:none] sm:px-6 lg:hidden [&::-webkit-scrollbar]:hidden"
            >
              {modules.map(({ key, icon: Icon, path }) =>
                path !== undefined ? (
                  <Link
                    key={key}
                    href={`/${locale}/admin${path}`}
                    aria-current={pathname === `/${locale}/admin${path}` ? "page" : undefined}
                    className={cn(item, "h-10 border border-line px-3 text-fg aria-[current=page]:border-accent aria-[current=page]:bg-accent aria-[current=page]:text-on-accent")}
                  >
                    <Icon size={16} strokeWidth={1.5} aria-hidden />
                    {t[key]}
                  </Link>
                ) : (
                  <span key={key} aria-disabled className={cn(item, "h-10 border border-line px-3 text-muted")}>
                    <Icon size={16} strokeWidth={1.5} aria-hidden />
                    {t[key]}
                  </span>
                ),
              )}
            </nav>
          </header>
          <main className="mx-auto max-w-[1000px] animate-rise px-5 pt-6 pb-16 sm:px-6 sm:pt-8">{children}</main>
        </div>
      </div>
    </AdminContext.Provider>
  );
}
