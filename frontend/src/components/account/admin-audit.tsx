"use client";

import { Filter, UserRound } from "lucide-react";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import type { Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";

import { AdminTitle, type ApiErr } from "./admin-ui";

type Entry = {
  id: number;
  occurred_at: string;
  actor_email: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  result: "success" | "failure" | "denied";
  ip_address: string | null;
  details: Record<string, unknown> | null;
};

const PAGE = 50;
const SCOPES = ["", "admin.", "auth.", "billing.", "trading.", "affiliate."] as const;
const TONE: Record<Entry["result"], BadgeTone> = { success: "gain", failure: "loss", denied: "warn" };

/** Journal non modifiable : lecture seule, par pages, et la lecture elle-même est journalisée. */
export function AdminAudit({ locale, messages }: { locale: Locale; messages: Messages }) {
  const t = messages.adminAudit;
  const f = formatters(locale);
  const [scope, setScope] = useState<(typeof SCOPES)[number]>("");
  const [actor, setActor] = useState("");
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [error, setError] = useState<ApiErr | null>(null);
  const [more, setMore] = useState(false);
  const [loading, setLoading] = useState(false);

  function query(before?: number) {
    const params = new URLSearchParams({ limit: String(PAGE) });
    if (scope) params.set("action", scope);
    if (actor.trim().includes("@")) params.set("actor", actor.trim());
    if (before) params.set("before", String(before));
    return `/admin/audit?${params}`;
  }

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      api<{ entries: Entry[] }>(query()).then((result) => {
        if (!active) return;
        if (result.ok) {
          setEntries(result.data.entries);
          setMore(result.data.entries.length === PAGE);
          setError(null);
        } else setError(result);
      });
    }, 300);
    return () => {
      active = false;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, actor]);

  async function loadMore() {
    const last = entries?.at(-1);
    if (!last) return;
    setLoading(true);
    const result = await api<{ entries: Entry[] }>(query(last.id));
    setLoading(false);
    if (!result.ok) return setError(result);
    setEntries([...(entries ?? []), ...result.data.entries]);
    setMore(result.data.entries.length === PAGE);
  }

  return (
    <>
      <AdminTitle title={messages.admin.audit} subtitle={t.subtitle} />
      <div className="mt-6 flex flex-col gap-3">
        <Field
          label={t.actor}
          icon={UserRound}
          placeholder={t.actorPlaceholder}
          value={actor}
          onChange={(event) => setActor(event.target.value)}
          type="email"
          inputMode="email"
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
        />
        <div role="group" aria-label={t.scope} className="flex items-center gap-2 overflow-x-auto pb-1 [scrollbar-width:none]">
          <Filter size={16} strokeWidth={1.5} aria-hidden className="shrink-0 text-muted" />
          {SCOPES.map((key) => (
            <button
              key={key || "all"}
              type="button"
              aria-pressed={scope === key}
              onClick={() => setScope(key)}
              className="h-11 shrink-0 rounded-lg border border-line bg-card px-4 text-label font-medium aria-pressed:border-accent aria-pressed:bg-accent aria-pressed:text-on-accent"
            >
              {t.scopes[(key.replace(".", "") || "all") as keyof typeof t.scopes]}
            </button>
          ))}
        </div>
      </div>
      {error && (
        <div className="mt-4">
          <Alert tone="error">{errorMessage(messages, error)}</Alert>
        </div>
      )}

      <Card className="mt-4 p-2 sm:p-3">
        {entries === null && !error && <p className="p-3 text-muted">{messages.trading.loading}</p>}
        {entries?.length === 0 && <p className="p-3 text-muted">{t.empty}</p>}
        <ul className="divide-y divide-line">
          {entries?.map((entry) => (
            <li key={entry.id} className="px-2 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <code className="min-w-0 truncate text-label font-medium">{entry.action}</code>
                <Badge tone={TONE[entry.result]}>{t.results[entry.result]}</Badge>
              </div>
              <p className="mt-1 text-small text-muted">
                {[f.dateTime(entry.occurred_at), entry.actor_email ?? t.system, entry.ip_address ?? t.noIp].join(" · ")}
              </p>
              {entry.details && Object.keys(entry.details).length > 0 && (
                <p className="mt-1 text-small break-all text-muted">
                  {Object.entries(entry.details)
                    .map(([key, value]) => `${key} : ${typeof value === "object" ? JSON.stringify(value) : String(value)}`)
                    .join(" · ")}
                </p>
              )}
            </li>
          ))}
        </ul>
      </Card>
      {more && (
        <div className="mt-4">
          <Button type="button" size="lg" pending={loading} onClick={loadMore} className="w-full sm:w-auto">
            {loading ? messages.trading.loading : t.more}
          </Button>
        </div>
      )}
    </>
  );
}
