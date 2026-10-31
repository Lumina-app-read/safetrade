"use client";

import { LayoutDashboard, LogOut, ShieldCheck, UserCog, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useRef, useState } from "react";

import type { Locale } from "@/i18n/config";
import type { Messages } from "@/i18n/messages";
import { api } from "@/lib/api";
import { isAdminRole } from "@/lib/roles";
import { useDismiss } from "@/lib/use-dismiss";

import { useSession } from "./session";

const itemClass = "flex h-11 w-full items-center gap-3 rounded-lg px-2.5 text-left text-body hover:bg-page";

export function UserMenu({ locale, messages, area }: { locale: Locale; messages: Messages; area: "app" | "admin" }) {
  const t = messages.shell;
  const { user } = useSession();
  const router = useRouter();
  const root = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(root, open, close);

  async function logout() {
    setLeaving(true);
    await api("/auth/logout", { method: "POST" });
    router.replace(`/${locale}/login`);
  }

  const links: Array<[string, string, LucideIcon]> = [[`/${locale}/account/security`, t.security, ShieldCheck]];
  if (area === "admin") links.unshift([`/${locale}/dashboard`, t.clientSpace, LayoutDashboard]);
  else if (isAdminRole(user.role)) links.push([`/${locale}/admin`, t.admin, UserCog]);

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t.userMenu}
        onClick={() => setOpen((v) => !v)}
        className="grid size-10 place-items-center rounded-full bg-accent-soft text-label font-medium text-accent-text uppercase focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        {user.first_name.slice(0, 1)}
      </button>
      <div
        role="menu"
        aria-label={t.userMenu}
        hidden={!open}
        className="absolute right-0 z-30 mt-2 w-64 animate-rise rounded-xl border border-line bg-card p-1.5 text-fg shadow-[0_12px_32px_-12px_var(--brand-ring)]"
      >
        <div className="border-b border-line px-2.5 pt-1.5 pb-2.5">
          <p className="truncate font-medium">{user.first_name}</p>
          <p className="truncate text-small text-muted">{user.email}</p>
        </div>
        <div className="flex flex-col pt-1.5">
          {links.map(([href, label, Icon]) => (
            <Link key={href} href={href} role="menuitem" onClick={close} className={itemClass}>
              <Icon size={18} strokeWidth={1.5} aria-hidden className="text-muted" />
              {label}
            </Link>
          ))}
          <button type="button" role="menuitem" onClick={logout} disabled={leaving} className={itemClass}>
            <LogOut size={18} strokeWidth={1.5} aria-hidden className="text-muted" />
            {t.logout}
          </button>
        </div>
      </div>
    </div>
  );
}
