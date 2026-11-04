"use client";

import { Eye, FileText, KeyRound, Megaphone, NotebookPen, RotateCcw, ShieldAlert, Trash2, Type } from "lucide-react";
import { useState, type FormEvent } from "react";

import { usePolled } from "@/components/trading/use-live";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useFormErrors } from "@/lib/use-form-errors";

import { ReasonAction, type ApiErr } from "./admin-ui";

const LANGS = ["fr", "en"] as const;
type Lang = (typeof LANGS)[number];

/** Zone de texte longue, avec les mêmes états que `Field`. */
function TextArea({
  label,
  name,
  defaultValue,
  rows = 4,
  maxLength,
  hint,
  error,
}: {
  label: string;
  name: string;
  defaultValue?: string;
  rows?: number;
  maxLength: number;
  hint?: string;
  error?: string;
}) {
  const id = `area-${name}`;
  return (
    <div data-field className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-label font-medium">
        {label}
      </label>
      <textarea
        id={id}
        name={name}
        rows={rows}
        maxLength={maxLength}
        defaultValue={defaultValue}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
        className={cn(
          "w-full rounded-lg border border-line bg-card px-3.5 py-3 text-[16px] leading-relaxed outline-none focus:border-accent focus:ring-4 focus:ring-brand-ring/30 sm:text-body",
          error && "border-loss",
        )}
      />
      {error ? (
        <p id={`${id}-error`} className="text-small text-loss">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="text-small text-muted">
            {hint}
          </p>
        )
      )}
    </div>
  );
}

function LangSwitch({ value, onChange, labels }: { value: Lang; onChange: (lang: Lang) => void; labels: Record<Lang, string> }) {
  return (
    <div role="group" className="flex gap-2">
      {LANGS.map((lang) => (
        <button
          key={lang}
          type="button"
          aria-pressed={value === lang}
          onClick={() => onChange(lang)}
          className="h-11 rounded-lg border border-line bg-card px-4 text-label font-medium aria-pressed:border-accent aria-pressed:bg-accent aria-pressed:text-on-accent"
        >
          {labels[lang]}
        </button>
      ))}
    </div>
  );
}

// Messages du site.

type MessagesData = {
  announcement: { enabled: boolean; tone: "info" | "warning"; fr: string; en: string } | null;
  risk_warning: { fr: string; en: string } | null;
};

export function MessagesPanel({ messages }: { messages: Messages }) {
  const t = messages.adminSettings.messages;
  const data = usePolled<MessagesData>("/admin/messages", 0);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ApiErr | null>(null);
  const [saved, setSaved] = useState(false);
  const { field, validate } = useFormErrors({
    note: (value) => (value.trim().length >= 5 ? undefined : messages.adminUi.noteInvalid),
  });
  if (!data.data) return <p className="text-muted">{data.error ? errorMessage(messages, data.error) : messages.trading.loading}</p>;
  const current = data.data;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(false);
    if (!validate(event.currentTarget)) return;
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "").trim();
    const hasAnnouncement = text("announcement_fr") || text("announcement_en");
    const hasWarning = text("warning_fr") || text("warning_en");
    setPending(true);
    setFailure(null);
    const result = await api("/admin/messages", {
      method: "PUT",
      body: {
        announcement: hasAnnouncement
          ? {
              enabled: form.get("enabled") === "on",
              tone: form.get("tone") === "warning" ? "warning" : "info",
              fr: text("announcement_fr"),
              en: text("announcement_en"),
            }
          : null,
        risk_warning: hasWarning ? { fr: text("warning_fr"), en: text("warning_en") } : null,
        note: text("note"),
      },
    });
    setPending(false);
    if (!result.ok) return setFailure(result);
    setSaved(true);
  }

  return (
    <Card className="p-5 sm:p-6">
      <form onSubmit={submit} noValidate className="flex flex-col gap-5">
        {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
        {saved && <Alert tone="success">{t.saved}</Alert>}
        <section className="flex flex-col gap-4">
          <h3 className="flex items-center gap-2 text-h3 font-medium">
            <Megaphone size={20} strokeWidth={1.5} aria-hidden />
            {t.announcement}
          </h3>
          <p className="text-small text-muted">{t.announcementBody}</p>
          <Checkbox name="enabled" label={t.enabled} defaultChecked={current.announcement?.enabled ?? false} />
          <fieldset className="flex flex-wrap gap-3">
            <legend className="mb-2 text-label font-medium">{t.tone}</legend>
            {(["info", "warning"] as const).map((tone) => (
              <label key={tone} className="flex min-h-11 items-center gap-2 rounded-lg border border-line px-3 has-checked:border-accent">
                <input type="radio" name="tone" value={tone} defaultChecked={(current.announcement?.tone ?? "info") === tone} className="size-4 accent-accent" />
                {t.tones[tone]}
              </label>
            ))}
          </fieldset>
          <TextArea label={t.textFr} name="announcement_fr" rows={2} maxLength={280} defaultValue={current.announcement?.fr} />
          <TextArea label={t.textEn} name="announcement_en" rows={2} maxLength={280} defaultValue={current.announcement?.en} />
        </section>
        <section className="flex flex-col gap-4 border-t border-line pt-5">
          <h3 className="flex items-center gap-2 text-h3 font-medium">
            <ShieldAlert size={20} strokeWidth={1.5} aria-hidden />
            {t.warning}
          </h3>
          <p className="text-small text-muted">{t.warningBody}</p>
          <TextArea label={t.textFr} name="warning_fr" rows={4} maxLength={1200} defaultValue={current.risk_warning?.fr} />
          <TextArea label={t.textEn} name="warning_en" rows={4} maxLength={1200} defaultValue={current.risk_warning?.en} />
        </section>
        <Field
          label={messages.adminUi.note}
          icon={NotebookPen}
          placeholder={messages.adminUi.notePlaceholder}
          autoComplete="off"
          maxLength={300}
          {...field("note")}
        />
        <Button type="submit" variant="primary" size="lg" pending={pending} className="w-full sm:w-auto sm:self-start">
          {pending ? t.saving : t.save}
        </Button>
      </form>
    </Card>
  );
}

// Textes légaux.

type LegalEntry = {
  kind: "legal_notice" | "terms" | "privacy" | "risk";
  locale: Lang;
  current: { title: string; body: string } | null;
  versions: Array<{ version: number; published_at: string; by: string | null }>;
};

export function LegalPanel({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.adminSettings.legal;
  const f = formatters(locale);
  const [version, setVersion] = useState(0);
  const data = usePolled<{ documents: LegalEntry[] }>(`/admin/legal?v=${version}`, 0);
  const [kind, setKind] = useState<LegalEntry["kind"]>("terms");
  const [lang, setLang] = useState<Lang>(locale);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ApiErr | null>(null);
  const [saved, setSaved] = useState(false);
  const { field, validate } = useFormErrors({
    title: (value) => (value.trim().length >= 3 ? undefined : t.titleInvalid),
    body: (value) => (value.trim().length >= 50 ? undefined : t.bodyInvalid),
    note: (value) => (value.trim().length >= 5 ? undefined : messages.adminUi.noteInvalid),
  });
  const entry = data.data?.documents.find((d) => d.kind === kind && d.locale === lang);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(false);
    if (!validate(event.currentTarget)) return;
    const form = new FormData(event.currentTarget);
    setPending(true);
    setFailure(null);
    const result = await api("/admin/legal", {
      body: {
        kind,
        locale: lang,
        title: String(form.get("title")).trim(),
        body: String(form.get("body")).trim(),
        note: String(form.get("note")).trim(),
      },
    });
    setPending(false);
    if (!result.ok) return setFailure(result);
    setSaved(true);
    setVersion((v) => v + 1);
  }

  return (
    <Card className="p-5 sm:p-6">
      <p className="text-small text-muted">{t.body}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {(["legal_notice", "terms", "privacy", "risk"] as const).map((key) => (
          <button
            key={key}
            type="button"
            aria-pressed={kind === key}
            onClick={() => setKind(key)}
            className="h-11 rounded-lg border border-line bg-card px-4 text-label font-medium aria-pressed:border-accent aria-pressed:bg-accent aria-pressed:text-on-accent"
          >
            {t.kinds[key]}
          </button>
        ))}
      </div>
      <div className="mt-3">
        <LangSwitch value={lang} onChange={setLang} labels={t.langs} />
      </div>
      <p className="mt-4 text-small text-muted">
        {entry?.versions.length
          ? interpolate(t.current, {
              version: entry.versions[0].version,
              date: f.dateTime(entry.versions[0].published_at),
              email: entry.versions[0].by ?? t.unknown,
            })
          : t.none}
      </p>
      <form key={`${kind}-${lang}-${version}`} onSubmit={submit} noValidate className="mt-4 flex flex-col gap-4">
        {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
        {saved && <Alert tone="success">{t.published}</Alert>}
        <Field label={t.title} icon={Type} defaultValue={entry?.current?.title ?? t.kinds[kind]} autoComplete="off" maxLength={150} {...field("title")} />
        <TextArea label={t.text} hint={t.textHint} rows={14} maxLength={60000} defaultValue={entry?.current?.body} {...field("body")} />
        <Field
          label={messages.adminUi.note}
          icon={NotebookPen}
          placeholder={messages.adminUi.notePlaceholder}
          autoComplete="off"
          maxLength={300}
          {...field("note")}
        />
        <div className="flex flex-wrap gap-3">
          <Button type="submit" variant="primary" size="lg" pending={pending}>
            <FileText size={18} strokeWidth={1.5} aria-hidden />
            {pending ? t.publishing : t.publish}
          </Button>
          <a
            href={`/${lang}/legal/${kind.replace("_", "-")}`}
            target="_blank"
            rel="noopener"
            className="inline-flex h-12 items-center gap-2 rounded-lg border border-line px-5 text-label font-medium hover:bg-page"
          >
            <Eye size={18} strokeWidth={1.5} aria-hidden />
            {t.view}
          </a>
        </div>
      </form>
      {entry && entry.versions.length > 1 && (
        <details className="mt-5">
          <summary className="min-h-11 cursor-pointer py-2 text-label font-medium">{interpolate(t.history, { count: entry.versions.length })}</summary>
          <ul className="mt-2 flex flex-col gap-1.5 text-small text-muted">
            {entry.versions.map((v) => (
              <li key={v.version}>{interpolate(t.versionLine, { version: v.version, date: f.dateTime(v.published_at), email: v.by ?? t.unknown })}</li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}

// E-mails types.

type Text = { subject: string; title: string; lines: string[]; note: string; action: string | null };
type Template = { template: string; langs: Record<Lang, { default: Text; current: Text; changed: boolean; placeholders: string[] }> };

export function EmailsPanel({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.adminSettings.emails;
  const [version, setVersion] = useState(0);
  const data = usePolled<{ templates: Template[] }>(`/admin/emails?v=${version}`, 0);
  const [selected, setSelected] = useState<string>("verify_email");
  const [lang, setLang] = useState<Lang>(locale);
  const [preview, setPreview] = useState<string | null>(null);
  const [pending, setPending] = useState<"save" | "preview" | null>(null);
  const [failure, setFailure] = useState<ApiErr | null>(null);
  const [saved, setSaved] = useState(false);
  const { field, validate } = useFormErrors({
    subject: (value) => (value.trim() ? undefined : t.required),
    title: (value) => (value.trim() ? undefined : t.required),
    lines: (value) => (value.trim() ? undefined : t.required),
    note: (value) => (value.trim() ? undefined : t.required),
    reason: (value) => (value.trim().length >= 5 ? undefined : messages.adminUi.noteInvalid),
  });
  const template = data.data?.templates.find((item) => item.template === selected);
  const text = template?.langs[lang];

  function values(form: HTMLFormElement) {
    const data = new FormData(form);
    return {
      subject: String(data.get("subject")).trim(),
      title: String(data.get("title")).trim(),
      lines: String(data.get("lines")).split(/\n\s*\n/).map((line) => line.replace(/\s*\n\s*/g, " ").trim()).filter(Boolean),
      note: String(data.get("note")).trim(),
      action: text?.default.action ? String(data.get("action") ?? "").trim() : null,
      reason: String(data.get("reason") ?? "").trim() || "aperçu",
    };
  }

  async function show(form: HTMLFormElement) {
    setPending("preview");
    setFailure(null);
    const result = await api<{ html: string }>(`/admin/emails/${selected}/${lang}/preview`, { body: values(form) });
    setPending(null);
    if (result.ok) setPreview(result.data.html);
    else setFailure(result);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(false);
    if (!validate(event.currentTarget)) return;
    setPending("save");
    setFailure(null);
    const result = await api(`/admin/emails/${selected}/${lang}`, { method: "PUT", body: values(event.currentTarget) });
    setPending(null);
    if (!result.ok) return setFailure(result);
    setSaved(true);
    setVersion((v) => v + 1);
  }

  return (
    <Card className="p-5 sm:p-6">
      <p className="text-small text-muted">{t.body}</p>
      <div className="mt-4 flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none]">
        {data.data?.templates.map((item) => (
          <button
            key={item.template}
            type="button"
            aria-pressed={selected === item.template}
            onClick={() => {
              setSelected(item.template);
              setPreview(null);
            }}
            className="h-11 shrink-0 rounded-lg border border-line bg-card px-4 text-label font-medium aria-pressed:border-accent aria-pressed:bg-accent aria-pressed:text-on-accent"
          >
            {t.names[item.template as keyof typeof t.names] ?? item.template}
          </button>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <LangSwitch value={lang} onChange={(value) => { setLang(value); setPreview(null); }} labels={messages.adminSettings.legal.langs} />
        {text && <Badge tone={text.changed ? "brand" : "neutral"}>{text.changed ? t.changed : t.original}</Badge>}
      </div>
      {text && (
        <form key={`${selected}-${lang}-${version}`} onSubmit={submit} noValidate className="mt-4 flex flex-col gap-4">
          {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
          {saved && <Alert tone="success">{t.saved}</Alert>}
          <Field label={t.subject} icon={Type} defaultValue={text.current.subject} autoComplete="off" maxLength={150} {...field("subject")} />
          <Field label={t.titleField} icon={Type} defaultValue={text.current.title} autoComplete="off" maxLength={150} {...field("title")} />
          <TextArea label={t.lines} hint={t.linesHint} rows={5} maxLength={4000} defaultValue={text.current.lines.join("\n\n")} {...field("lines")} />
          {text.default.action && (
            <Field label={t.action} icon={Type} defaultValue={text.current.action ?? ""} autoComplete="off" maxLength={60} name="action" />
          )}
          <TextArea
            label={t.note}
            hint={text.placeholders.length ? interpolate(t.noteHint, { names: text.placeholders.map((name) => `{${name}}`).join(", ") }) : t.noteNoVars}
            rows={2}
            maxLength={400}
            defaultValue={text.current.note}
            {...field("note")}
          />
          <Field
            label={messages.adminUi.note}
            icon={NotebookPen}
            placeholder={messages.adminUi.notePlaceholder}
            autoComplete="off"
            maxLength={300}
            {...field("reason")}
          />
          <div className="flex flex-wrap gap-3">
            <Button type="submit" variant="primary" size="lg" pending={pending === "save"}>
              {pending === "save" ? t.saving : t.save}
            </Button>
            <Button type="button" size="lg" pending={pending === "preview"} onClick={(event) => show(event.currentTarget.form as HTMLFormElement)}>
              <Eye size={18} strokeWidth={1.5} aria-hidden />
              {t.preview}
            </Button>
          </div>
          {text.changed && (
            <ReasonAction
              messages={messages}
              label={t.reset}
              confirm={t.confirmReset}
              pending={t.saving}
              icon={RotateCcw}
              onSubmit={(reason) => api(`/admin/emails/${selected}/${lang}/reset`, { body: { reason } })}
              onDone={() => setVersion((v) => v + 1)}
            />
          )}
        </form>
      )}
      {preview && (
        <div className="mt-5">
          <p className="mb-2 text-label font-medium">{t.previewTitle}</p>
          {/* Aperçu isolé : aucun script, aucun lien actif. */}
          <iframe title={t.previewTitle} sandbox="" srcDoc={preview} className="h-[520px] w-full rounded-lg border border-line bg-page" />
        </div>
      )}
    </Card>
  );
}

// Clés des services externes.

type KeyRow = { name: string; secret: boolean; source: "admin" | "environment" | null; value: string | null; updated_at: string | null; updated_by: string | null };
type KeysData = { editable: KeyRow[]; environment: Array<{ name: string; configured: boolean }>; encryption: boolean };

export function KeysPanel({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.adminSettings.keys;
  const f = formatters(locale);
  const polled = usePolled<KeysData>("/admin/keys", 0);
  const [override, setOverride] = useState<KeysData | null>(null);
  const data = override ?? polled.data;
  if (!data) return <p className="text-muted">{polled.error ? errorMessage(messages, polled.error) : messages.trading.loading}</p>;

  return (
    <div className="flex flex-col gap-4">
      <Alert tone={data.encryption ? "info" : "error"}>{data.encryption ? t.encrypted : t.noEncryption}</Alert>
      {data.editable.map((key) => (
        <KeyCard key={`${key.name}-${key.updated_at}`} entry={key} locale={locale} messages={messages} onSaved={setOverride} />
      ))}
      <Card className="p-5 sm:p-6">
        <h3 className="text-h3 font-medium">{t.environment}</h3>
        <p className="mt-1 text-small text-muted">{t.environmentBody}</p>
        <ul className="mt-3 divide-y divide-line">
          {data.environment.map((item) => (
            <li key={item.name} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <span>{t.names[item.name as keyof typeof t.names] ?? item.name}</span>
              <Badge tone={item.configured ? "gain" : "warn"}>{item.configured ? t.configured : t.missing}</Badge>
            </li>
          ))}
        </ul>
      </Card>
      <p className="text-small text-muted">{interpolate(t.footnote, { date: f.date(new Date()) })}</p>
    </div>
  );
}

function KeyCard({ entry, locale, messages, onSaved }: { entry: KeyRow; locale: Locale; messages: Messages; onSaved: (data: KeysData) => void }) {
  const t = messages.adminSettings.keys;
  const f = formatters(locale);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ApiErr | null>(null);
  const { field, validate } = useFormErrors({
    value: (value) => (value.trim() && !/\s/.test(value.trim()) ? undefined : t.valueInvalid),
    note: (value) => (value.trim().length >= 5 ? undefined : messages.adminUi.noteInvalid),
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    if (!validate(element)) return;
    const form = new FormData(element);
    setPending(true);
    setFailure(null);
    const result = await api<KeysData>(`/admin/keys/${entry.name}`, {
      method: "PUT",
      body: { value: String(form.get("value")).trim(), note: String(form.get("note")).trim() },
    });
    setPending(false);
    if (!result.ok) return setFailure(result);
    element.reset();
    onSaved(result.data);
  }

  const source =
    entry.source === "admin"
      ? interpolate(t.fromAdmin, { date: entry.updated_at ? f.dateTime(entry.updated_at) : t.unknown, email: entry.updated_by ?? t.unknown })
      : entry.source === "environment"
        ? t.fromEnvironment
        : t.notSet;

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-h3 font-medium">{t.names[entry.name as keyof typeof t.names] ?? entry.name}</h3>
          <p className="mt-1 text-small text-muted">{source}</p>
          {entry.value && <p className="mt-1 truncate font-mono text-small">{entry.value}</p>}
        </div>
        <Badge tone={entry.source ? "gain" : "warn"}>{entry.source ? t.configured : t.missing}</Badge>
      </div>
      <form onSubmit={submit} noValidate className="mt-4 flex flex-col gap-3">
        {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
        <Field
          label={entry.source ? t.replace : t.set}
          icon={KeyRound}
          placeholder={entry.secret ? t.secretPlaceholder : t.valuePlaceholder}
          type={entry.secret ? "password" : "text"}
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          maxLength={300}
          {...field("value")}
        />
        <Field label={messages.adminUi.note} icon={NotebookPen} placeholder={messages.adminUi.notePlaceholder} autoComplete="off" maxLength={300} {...field("note")} />
        <div className="flex flex-wrap gap-3">
          <Button type="submit" variant="primary" size="lg" pending={pending}>
            {pending ? t.saving : t.save}
          </Button>
        </div>
      </form>
      {entry.source === "admin" && (
        <div className="mt-3">
          <ReasonAction
            messages={messages}
            label={t.remove}
            confirm={t.confirmRemove}
            pending={t.saving}
            icon={Trash2}
            variant="danger"
            onSubmit={(note) => api<KeysData>(`/admin/keys/${entry.name}/remove`, { body: { note } })}
            onDone={onSaved}
          />
        </div>
      )}
    </Card>
  );
}
