"use client";

import { Search, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import { interpolate, type Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";

import type { Asset } from "./types";

type GroupKey = keyof Messages["trading"]["assets"]["groups"];

// La liste vient de Deriv ; seul le classement par famille est défini ici.
const GROUPS: Array<{ key: GroupKey; submarkets: string[]; sudden?: boolean }> = [
  { key: "volatility", submarkets: ["random_index"] },
  { key: "crashBoom", submarkets: ["crash_index"], sudden: true },
  { key: "jump", submarkets: ["jump_index"], sudden: true },
  { key: "step", submarkets: ["step_index"] },
  { key: "range", submarkets: ["range_index"] },
  { key: "baskets", submarkets: ["forex_basket", "commodity_basket"] },
  { key: "daily", submarkets: ["random_daily"] },
];
const CLASSIFIED = new Set(GROUPS.flatMap((group) => group.submarkets));

/** Choix des actifs de la barre. Enregistré par le backend, qui revalide chaque actif. */
export function AssetPicker({
  assets,
  watched,
  messages,
  onSaved,
}: {
  assets: Asset[];
  watched: string[];
  messages: Messages;
  onSaved: () => void;
}) {
  const t = messages.trading.assets;
  const [chosen, setChosen] = useState(watched);
  const [query, setQuery] = useState("");
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<{ code: string; retryAfter?: number } | null>(null);

  const sections = useMemo(() => {
    const term = query.trim().toLowerCase();
    const found = assets
      .filter((asset) => asset.name.toLowerCase().includes(term) || asset.symbol.toLowerCase().includes(term))
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
    const groups = GROUPS.map((group) => ({
      ...group,
      rows: found.filter((asset) => group.submarkets.includes(asset.submarket ?? "")),
    }));
    const others = found.filter((asset) => !CLASSIFIED.has(asset.submarket ?? ""));
    return [...groups, { key: "other" as GroupKey, submarkets: [], rows: others }].filter((group) => group.rows.length > 0);
  }, [assets, query]);

  function toggle(symbol: string, on: boolean) {
    setChosen((current) => (on ? [...current, symbol] : current.filter((value) => value !== symbol)));
  }

  function toggleGroup(symbols: string[], on: boolean) {
    setChosen((current) => {
      const rest = current.filter((value) => !symbols.includes(value));
      return on ? [...rest, ...symbols] : rest;
    });
  }

  async function save() {
    setPending(true);
    setFailure(null);
    const result = await api("/market/watchlist", { method: "PUT", body: { symbols: chosen } });
    setPending(false);
    if (result.ok) onSaved();
    else setFailure(result);
  }

  return (
    <div className="flex flex-col gap-4">
      <Field
        label={t.search}
        icon={Search}
        placeholder={t.searchPlaceholder}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        autoComplete="off"
        spellCheck={false}
        enterKeyHint="search"
      />
      {sections.length === 0 && <p className="text-muted">{t.noResult}</p>}
      {sections.map(({ key, rows, sudden }) => {
        const symbols = rows.map((asset) => asset.symbol);
        const allOn = symbols.every((symbol) => chosen.includes(symbol));
        return (
          <section key={key} className="flex flex-col">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-small font-medium tracking-[0.08em] text-muted uppercase">{t.groups[key]}</h3>
              <button
                type="button"
                onClick={() => toggleGroup(symbols, !allOn)}
                className="min-h-11 shrink-0 px-1 text-label font-medium text-accent-text underline-offset-4 hover:underline"
              >
                {allOn ? t.removeAll : t.addAll}
              </button>
            </div>
            {sudden && (
              <p className="mb-1 flex items-start gap-2 text-small text-muted">
                <TriangleAlert size={14} strokeWidth={1.5} aria-hidden className="mt-0.5 shrink-0 text-warn" />
                {t.suddenNote}
              </p>
            )}
            <ul className="grid sm:grid-cols-2 sm:gap-x-4">
              {rows.map((asset) => (
                <li key={asset.symbol} className="min-w-0">
                  <Checkbox label={asset.name} checked={chosen.includes(asset.symbol)} onChange={(event) => toggle(asset.symbol, event.target.checked)} />
                  {asset.multipliers === false && <p className="-mt-1 mb-1 pl-7.5 text-small text-muted">{t.noBot}</p>}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
      <div className="sticky bottom-0 -mx-5 flex flex-col gap-2 border-t border-line bg-card px-5 py-3 sm:-mx-6 sm:px-6">
        {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}
        {chosen.length === 0 && <p className="text-small text-loss">{t.required}</p>}
        <Button variant="primary" size="lg" pending={pending} disabled={chosen.length === 0} className="w-full" onClick={save}>
          {interpolate(t.save, { count: chosen.length })}
        </Button>
      </div>
    </div>
  );
}
