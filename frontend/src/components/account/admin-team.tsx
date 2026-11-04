"use client";

import { Mail, NotebookPen, ShieldCheck, ShieldOff, UserCog } from "lucide-react";
import { useState, type FormEvent } from "react";

import { useAdmin } from "@/components/shell/admin-shell";
import { usePolled } from "@/components/trading/use-live";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, SectionTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import type { Locale } from "@/i18n/config";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { useFormErrors } from "@/lib/use-form-errors";
import { emailRule } from "@/lib/validation";

import { AdminTitle, ReasonAction, type ApiErr } from "./admin-ui";
import { roleName } from "./admin-users";

type Member = {
  id: string;
  email: string;
  first_name: string;
  role: string;
  status: string;
  mfa_enabled: boolean;
  permissions: string[];
};

/** Équipe : rôles au moindre privilège. Un compte existant, à l'e-mail vérifié, reçoit un rôle. */
export function AdminTeam({ messages }: { locale: Locale; messages: Messages }) {
  const t = messages.adminTeam;
  const { user: me } = useAdmin();
  const [version, setVersion] = useState(0);
  const data = usePolled<{ members: Member[]; roles: string[] }>(`/admin/team?v=${version}`, 0);
  const refresh = () => setVersion((v) => v + 1);

  return (
    <>
      <AdminTitle title={messages.admin.team} subtitle={t.subtitle} />
      {data.error && !data.data && (
        <div className="mt-6">
          <Alert tone="error">{errorMessage(messages, data.error)}</Alert>
        </div>
      )}

      <SectionTitle>{interpolate(t.members, { count: data.data?.members.length ?? 0 })}</SectionTitle>
      <Card className="p-2 sm:p-3">
        <ul className="divide-y divide-line">
          {data.data?.members.map((member) => (
            <li key={member.id} className="flex flex-col gap-3 px-2 py-3">
              <div className="flex flex-wrap items-center gap-3">
                <span className="grid size-10 shrink-0 place-items-center rounded-full bg-page text-label font-medium uppercase">
                  {member.first_name.slice(0, 1)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{member.first_name}</p>
                  <p className="truncate text-small text-muted">{member.email}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge tone="brand">{roleName(messages, member.role)}</Badge>
                  <Badge tone={member.mfa_enabled ? "gain" : "warn"}>{member.mfa_enabled ? t.mfaOn : t.mfaOff}</Badge>
                </div>
              </div>
              <p className="text-small text-muted">{interpolate(t.permissionsCount, { count: member.permissions.length })}</p>
              {member.id !== me.id && (
                <ReasonAction
                  messages={messages}
                  label={t.remove}
                  confirm={t.confirmRemove}
                  pending={t.working}
                  icon={ShieldOff}
                  variant="danger"
                  onSubmit={(note) => api(`/admin/team/${member.id}`, { method: "PUT", body: { role: "client", note } })}
                  onDone={refresh}
                />
              )}
            </li>
          ))}
        </ul>
      </Card>

      <SectionTitle>{t.addTitle}</SectionTitle>
      <AddMember roles={data.data?.roles ?? []} messages={messages} onDone={refresh} />
    </>
  );
}

function AddMember({ roles, messages, onDone }: { roles: string[]; messages: Messages; onDone: () => void }) {
  const t = messages.adminTeam;
  const [role, setRole] = useState("support");
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ApiErr | null>(null);
  const [saved, setSaved] = useState(false);
  const { field, validate } = useFormErrors({
    email: emailRule(messages.auth.validation),
    note: (value) => (value.trim().length >= 5 ? undefined : messages.adminUi.noteInvalid),
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    setSaved(false);
    if (!validate(element)) return;
    const form = new FormData(element);
    const email = String(form.get("email")).trim().toLowerCase();
    setPending(true);
    setFailure(null);
    // Le compte est retrouvé par le serveur ; aucune donnée n'est déduite côté navigateur.
    const found = await api<{ users: Array<{ id: string; email: string }> }>(`/admin/users?q=${encodeURIComponent(email)}&limit=5`);
    const target = found.ok ? found.data.users.find((u) => u.email.toLowerCase() === email) : undefined;
    if (!found.ok || !target) {
      setPending(false);
      setFailure(found.ok ? { code: "admin.user_not_found" } : found);
      return;
    }
    const result = await api(`/admin/team/${target.id}`, { method: "PUT", body: { role, note: String(form.get("note")).trim() } });
    setPending(false);
    if (!result.ok) return setFailure(result);
    setSaved(true);
    element.reset();
    onDone();
  }

  return (
    <Card className="p-5 sm:p-6">
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <p className="max-w-2xl text-small text-muted">{t.addBody}</p>
        {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
        {saved && <Alert tone="success">{t.added}</Alert>}
        <Field
          label={t.email}
          icon={Mail}
          placeholder={messages.auth.login.emailPlaceholder}
          type="email"
          inputMode="email"
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          {...field("email")}
        />
        <fieldset>
          <legend className="mb-2 text-label font-medium">{t.role}</legend>
          <div className="grid gap-2 sm:grid-cols-3">
            {roles.map((code) => (
              <label
                key={code}
                className="flex min-h-12 cursor-pointer items-start gap-3 rounded-lg border border-line bg-card p-3 has-checked:border-accent has-checked:bg-accent-soft"
              >
                <input
                  type="radio"
                  name="role"
                  value={code}
                  checked={role === code}
                  onChange={() => setRole(code)}
                  className="mt-1 size-4 accent-accent"
                />
                <span className="min-w-0">
                  <span className="flex items-center gap-1.5 text-label font-medium">
                    {code === "super_admin" ? (
                      <ShieldCheck size={16} strokeWidth={1.5} aria-hidden />
                    ) : (
                      <UserCog size={16} strokeWidth={1.5} aria-hidden />
                    )}
                    {roleName(messages, code)}
                  </span>
                  <span className="mt-0.5 block text-small text-muted">
                    {t.roleHints[code as keyof typeof t.roleHints] ?? ""}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <Field
          label={messages.adminUi.note}
          icon={NotebookPen}
          placeholder={messages.adminUi.notePlaceholder}
          autoComplete="off"
          maxLength={300}
          {...field("note")}
        />
        <Button type="submit" variant="primary" size="lg" pending={pending} className="w-full sm:w-auto sm:self-start">
          {pending ? t.working : t.add}
        </Button>
      </form>
    </Card>
  );
}
