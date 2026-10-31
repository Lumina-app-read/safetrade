"use client";

import { TriangleAlert } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import type { Locale } from "@/i18n/config";
import { browserTimeZone, formatters } from "@/i18n/format";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";
import { useFormErrors } from "@/lib/use-form-errors";
import type { Rule } from "@/lib/validation";

import type { Asset, SettingsResponse } from "./types";

const GROUPS: Array<{ title: "groupPosition" | "groupLimits" | "groupPause" | "groupDynamic"; fields: string[] }> = [
  { title: "groupPosition", fields: ["stake", "multiplier", "stop_loss_pct", "capital_pct", "max_positions"] },
  { title: "groupLimits", fields: ["session_target_pct", "session_loss_pct", "daily_target_pct", "daily_loss_pct"] },
  { title: "groupPause", fields: ["max_consecutive_losses", "pause_minutes"] },
  { title: "groupDynamic", fields: ["activation_r", "locked_fraction"] },
];

const INTEGER = new Set(["multiplier", "max_positions", "max_consecutive_losses", "pause_minutes"]);

function normalize(value: string): string {
  return value.trim().replace(",", ".");
}

/** Paramètres de risque. Les plages viennent du backend, qui revalide tout à l'enregistrement. */
export function SettingsForm({
  data,
  assets,
  locale,
  messages,
  onSaved,
}: {
  data: SettingsResponse;
  assets: Asset[];
  locale: Locale;
  messages: Messages;
  onSaved: () => void;
}) {
  const t = messages.trading.settings;
  const f = formatters(locale);
  const labels = t.fields as Record<string, string>;
  const [allowed, setAllowed] = useState<string[]>(data.settings.allowed_symbols as string[]);
  const [everyAsset, setEveryAsset] = useState(data.settings.all_symbols === true);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<{ code: string; retryAfter?: number } | null>(null);
  const [saved, setSaved] = useState(false);
  const [symbolsError, setSymbolsError] = useState(false);

  const rules: Record<string, Rule> = Object.fromEntries(
    Object.entries(data.ranges).map(([name, range]) => [
      name,
      (raw: string) => {
        const value = Number(normalize(raw));
        const inRange = raw.trim() !== "" && !Number.isNaN(value) && value >= Number(range.min) && value <= Number(range.max);
        if (!inRange || (INTEGER.has(name) && !Number.isInteger(value))) {
          return interpolate(t.outOfRange, { min: f.number(Number(range.min)), max: f.number(Number(range.max)) });
        }
        return undefined;
      },
    ]),
  );
  const { field, validate, setError } = useFormErrors(rules);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(false);
    const ok = validate(event.currentTarget);
    const noAsset = !everyAsset && allowed.length === 0;
    setSymbolsError(noAsset);
    if (!ok || noAsset) return;
    const form = new FormData(event.currentTarget);
    const values = Object.fromEntries(Object.keys(data.ranges).map((name) => [name, normalize(String(form.get(name)))]));
    setPending(true);
    setFailure(null);
    const result = await api("/trading/settings", {
      method: "PUT",
      body: {
        ...values,
        all_symbols: everyAsset,
        // Le serveur exige une liste : elle est conservée pour le jour où le client restreint.
        allowed_symbols: allowed.length ? allowed : assets.map((asset) => asset.symbol),
        timezone: browserTimeZone(),
      },
    });
    setPending(false);
    if (result.ok) {
      setSaved(true);
      onSaved();
      return;
    }
    // Champ refusé par le serveur : l'erreur s'affiche sous ce champ.
    const known = result.fields?.filter((name) => name in data.ranges) ?? [];
    known.forEach((name) => setError(name, messages.errors.trading_invalid_settings));
    if (known.length === 0) setFailure(result);
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-6">
      {GROUPS.map(({ title, fields }) => (
        <fieldset key={title} className="flex flex-col gap-3">
          <legend className="mb-1 text-label font-medium text-muted">{t[title]}</legend>
          {title === "groupDynamic" && (
            <p className="flex items-start gap-2 rounded-lg bg-warn-soft p-3 text-small text-fg">
              <TriangleAlert size={16} strokeWidth={1.5} aria-hidden className="mt-px shrink-0 text-warn" />
              {t.provisional}
            </p>
          )}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {fields.map((name) => (
              <Field
                key={name}
                label={labels[name]}
                defaultValue={Number(data.settings[name])}
                inputMode={INTEGER.has(name) ? "numeric" : "decimal"}
                autoComplete="off"
                hint={interpolate(t.rangeHint, { min: f.number(Number(data.ranges[name].min)), max: f.number(Number(data.ranges[name].max)) })}
                {...field(name)}
              />
            ))}
          </div>
        </fieldset>
      ))}

      <fieldset className="flex flex-col gap-1">
        <legend className="mb-1 text-label font-medium text-muted">{t.groupAssets}</legend>
        <Checkbox label={t.everyAsset} checked={everyAsset} onChange={(event) => setEveryAsset(event.target.checked)} />
        {!everyAsset && assets.map((asset) => (
          <Checkbox
            key={asset.symbol}
            label={asset.name}
            checked={allowed.includes(asset.symbol)}
            onChange={(event) => {
              const next = event.target.checked ? [...allowed, asset.symbol] : allowed.filter((s) => s !== asset.symbol);
              setAllowed(next);
              setSymbolsError(next.length === 0);
            }}
          />
        ))}
        {!everyAsset && symbolsError && <p className="text-small text-loss">{t.assetsRequired}</p>}
      </fieldset>

      {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
      {saved && <Alert tone="success">{t.saved}</Alert>}
      <p className="text-small text-muted">{t.appliesNext}</p>
      <Button type="submit" variant="primary" size="lg" pending={pending} className="w-full">
        {pending ? t.saving : t.save}
      </Button>
    </form>
  );
}
