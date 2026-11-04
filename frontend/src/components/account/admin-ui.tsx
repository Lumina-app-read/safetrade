"use client";

import { NotebookPen, type LucideIcon } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { FitValue } from "@/components/ui/fit-value";
import type { Messages } from "@/i18n/messages";
import { errorMessage, type ApiResult } from "@/lib/api";
import { useFormErrors } from "@/lib/use-form-errors";

export type ApiErr = { code: string; retryAfter?: number };

/** En-tête d'un module d'administration. */
export function AdminTitle({ title, subtitle, action }: { title: string; subtitle: string; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-h1">{title}</h1>
        <p className="mt-1 text-muted">{subtitle}</p>
      </div>
      {action}
    </div>
  );
}

/** Chiffre clé d'un tableau de bord : la taille s'adapte, la valeur ne déborde jamais. */
export function StatTile({ label, value, icon: Icon, hint }: { label: string; value: string; icon: LucideIcon; hint?: string }) {
  return (
    <Card className="flex min-w-0 flex-col gap-3 p-4 sm:p-6">
      <div className="flex items-center justify-between gap-2">
        <p className="text-small text-muted">{label}</p>
        <Icon size={20} strokeWidth={1.5} aria-hidden className="shrink-0 text-muted" />
      </div>
      <FitValue text={value} />
      {hint && <p className="text-small text-muted">{hint}</p>}
    </Card>
  );
}

/** Ligne libellé et valeur d'une fiche. */
export function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5 py-2.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
      <dt className="shrink-0 text-small text-muted">{label}</dt>
      <dd className="min-w-0 break-words sm:text-right">{children}</dd>
    </div>
  );
}

/**
 * Action sensible : un bouton qui ouvre un motif obligatoire, puis la confirmation.
 * Le serveur revérifie le droit et exige lui aussi le motif.
 */
export function ReasonAction<T>({
  messages,
  label,
  confirm,
  pending: pendingLabel,
  icon: Icon,
  variant = "ghost",
  onSubmit,
  onDone,
}: {
  messages: Messages;
  label: string;
  confirm: string;
  pending: string;
  icon: LucideIcon;
  variant?: "ghost" | "danger" | "primary" | "accent";
  onSubmit: (note: string) => Promise<ApiResult<T>>;
  onDone: (data: T) => void;
}) {
  const t = messages.adminUi;
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ApiErr | null>(null);
  const { field, validate } = useFormErrors({
    note: (value) => (value.trim().length >= 5 ? undefined : t.noteInvalid),
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validate(event.currentTarget)) return;
    const note = String(new FormData(event.currentTarget).get("note")).trim();
    setPending(true);
    setFailure(null);
    const result = await onSubmit(note);
    setPending(false);
    if (!result.ok) return setFailure(result);
    setOpen(false);
    onDone(result.data);
  }

  if (!open) {
    return (
      <Button type="button" variant={variant} size="lg" onClick={() => setOpen(true)} className="w-full sm:w-auto">
        <Icon size={18} strokeWidth={1.5} aria-hidden />
        {label}
      </Button>
    );
  }
  return (
    <form onSubmit={submit} noValidate className="flex w-full flex-col gap-3 rounded-xl border border-line bg-page p-4">
      {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
      <Field
        label={t.note}
        icon={NotebookPen}
        placeholder={t.notePlaceholder}
        hint={t.noteHint}
        autoComplete="off"
        maxLength={300}
        enterKeyHint="send"
        autoFocus
        {...field("note")}
      />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant={variant === "ghost" ? "primary" : variant} size="lg" pending={pending}>
          {pending ? pendingLabel : confirm}
        </Button>
        <Button type="button" size="lg" onClick={() => setOpen(false)}>
          {t.cancel}
        </Button>
      </div>
    </form>
  );
}
