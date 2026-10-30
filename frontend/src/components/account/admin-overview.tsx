"use client";

import { KeyRound, ShieldCheck, UserCog } from "lucide-react";
import { useEffect, useState } from "react";

import { useAdmin } from "@/components/shell/admin-shell";
import { Badge } from "@/components/ui/badge";
import { Card, SectionTitle } from "@/components/ui/card";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { api } from "@/lib/api";

type UserRow = { id: string; email: string; first_name: string; status: string; created_at: string };

/** Vue d'ensemble : données réelles de l'API ; les indicateurs complets arrivent en phase 5. */
export function AdminOverview({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.admin;
  const { user, permissions } = useAdmin();
  const f = formatters(locale);
  const canReadUsers = permissions.includes("users.read");
  const [users, setUsers] = useState<UserRow[] | null>(null);

  useEffect(() => {
    if (!canReadUsers) return;
    let active = true;
    api<{ users: UserRow[] }>("/admin/users?limit=5").then((result) => {
      if (active && result.ok) setUsers(result.data.users);
    });
    return () => {
      active = false;
    };
  }, [canReadUsers]);

  const roleLabels: Record<string, string> = {
    super_admin: t.roleSuper,
    support: t.roleSupport,
    finance: t.roleFinance,
  };
  const tiles = [
    { label: t.role, value: roleLabels[user.role] ?? user.role, icon: UserCog },
    { label: t.mfa, value: t.mfaOn, icon: ShieldCheck },
    { label: t.permissions, value: interpolate(t.permissionsCount, { count: permissions.length }), icon: KeyRound },
  ];

  return (
    <>
      <h1 className="text-h1">{t.title}</h1>
      <p className="mt-1 text-muted">{t.subtitle}</p>

      <div className="mt-6 grid gap-3 sm:grid-cols-3 sm:gap-4">
        {tiles.map(({ label, value, icon: Icon }) => (
          <Card key={label} className="flex items-center gap-4 p-4 sm:flex-col sm:items-start sm:p-6">
            <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent-text">
              <Icon size={20} strokeWidth={1.5} aria-hidden />
            </span>
            <div className="min-w-0">
              <p className="text-small text-muted">{label}</p>
              <p className="truncate text-h3 font-medium">{value}</p>
            </div>
          </Card>
        ))}
      </div>

      {canReadUsers && (
        <>
          <SectionTitle>{t.recentUsers}</SectionTitle>
          <Card className="p-2 sm:p-3">
            {users?.length === 0 && <p className="p-3 text-muted">{t.noUsers}</p>}
            <ul className="divide-y divide-line">
              {users?.map((u) => (
                <li key={u.id} className="flex min-h-16 items-center gap-3 px-2 py-2.5">
                  <span className="grid size-10 shrink-0 place-items-center rounded-full bg-page text-label font-medium uppercase">
                    {u.first_name.slice(0, 1)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{u.first_name}</p>
                    <p className="truncate text-small text-muted">{u.email}</p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <Badge tone={u.status === "active" ? "gain" : "loss"}>
                      {u.status === "active" ? t.statusActive : t.statusSuspended}
                    </Badge>
                    <span className="text-small text-muted">{f.date(u.created_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}
    </>
  );
}
