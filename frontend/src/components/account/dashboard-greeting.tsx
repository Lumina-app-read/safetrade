"use client";

import { LogOut, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import type { Locale } from "@/i18n/config";
import { interpolate, type Messages } from "@/i18n/messages";
import { api } from "@/lib/api";

type Me = { user: { first_name: string } };

/** Coquille provisoire du tableau de bord (étape 1.8) : session vérifiée par le serveur. */
export function DashboardGreeting({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.dashboard;
  const router = useRouter();
  const [name, setName] = useState<string | null>(null);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    let active = true;
    api<Me>("/auth/me").then((result) => {
      if (!active) return;
      if (result.ok) setName(result.data.user.first_name);
      else router.replace(`/${locale}/login`);
    });
    return () => {
      active = false;
    };
  }, [locale, router]);

  async function logout() {
    setLeaving(true);
    await api("/auth/logout", { method: "POST" });
    router.replace(`/${locale}/login`);
  }

  if (name === null) {
    return (
      <p role="status" className="animate-fade text-muted">
        {t.loading}
      </p>
    );
  }
  return (
    <div className="flex animate-rise flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {/* Seul emoji autorisé de l'interface (section 15). */}
        <h1 className="text-h1">
          {interpolate(t.greeting, { name })} <span aria-hidden>👋</span>
        </h1>
        <p className="mt-1 text-muted">{t.subtitle}</p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <a
          href={`/${locale}/account/security`}
          className="inline-flex h-12 items-center justify-center gap-2 rounded-lg border border-line bg-card px-5 text-label font-medium hover:bg-page"
        >
          <ShieldCheck size={18} strokeWidth={1.5} aria-hidden />
          {messages.security.nav}
        </a>
        <Button size="lg" icon={<LogOut size={18} strokeWidth={1.5} aria-hidden />} pending={leaving} onClick={logout}>
          {t.logout}
        </Button>
      </div>
    </div>
  );
}
