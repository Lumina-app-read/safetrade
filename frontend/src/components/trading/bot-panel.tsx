"use client";

import { CirclePause, CirclePlay, CircleStop, Lock, Octagon, Bot, type LucideIcon } from "lucide-react";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import type { Messages } from "@/i18n/messages";
import { api, errorMessage } from "@/lib/api";

import { codeText } from "./labels";
import type { Asset, BotResponse, BotState } from "./types";

const TONES: Record<BotState, BadgeTone> = {
  starting: "neutral",
  analyzing: "neutral",
  position_open: "neutral",
  paused: "warn",
  target_reached: "gain",
  limit_reached: "warn",
  error: "loss",
  stopping: "neutral",
  stopped: "neutral",
};

type Failure = { code: string; retryAfter?: number };

function Action({
  icon: Icon,
  label,
  onClick,
  disabled,
  pending,
  variant = "ghost",
}: {
  icon: LucideIcon;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  pending?: boolean;
  variant?: "ghost" | "accent" | "danger" | "primary";
}) {
  return (
    <Button size="lg" variant={variant} className="w-full" onClick={onClick} disabled={disabled} pending={pending}>
      {!pending && <Icon size={18} strokeWidth={1.5} aria-hidden />}
      <span className="min-w-0 truncate">{label}</span>
    </Button>
  );
}

/** Pilotage du bot. Rien n'est simulé : l'état affiché est toujours celui du backend. */
export function BotPanel({
  bot,
  asset,
  canTrade,
  blocked,
  onChanged,
  messages,
}: {
  bot: BotResponse | null;
  asset: Asset | undefined;
  canTrade: boolean;
  blocked: string | null;
  onChanged: () => void;
  messages: Messages;
}) {
  const t = messages.trading.bot;
  const [pending, setPending] = useState<string | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [confirming, setConfirming] = useState(false);

  const session = bot?.session ?? null;
  const state: BotState = session?.state ?? "stopped";
  const waiting = Boolean(session?.command);
  const hasPositions = (bot?.open_positions.length ?? 0) > 0;

  async function run(key: string, call: () => Promise<{ ok: true } | ({ ok: false } & Failure)>) {
    setPending(key);
    setFailure(null);
    const result = await call();
    setPending(null);
    if (!result.ok) setFailure(result);
    onChanged();
  }

  const command = (name: string) =>
    run(name, () => api(`/trading/bot/command/${name}`, { method: "POST" }));
  const start = () => run("start", () => api("/trading/bot/start", { body: { symbol: asset?.symbol } }));

  const canPause = state === "analyzing" || state === "position_open";
  const canStop = session !== null && state !== "stopping";
  const finished = bot?.last_session;

  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-h3 font-medium">
          <Bot size={20} strokeWidth={1.5} aria-hidden className="text-muted" />
          {t.title}
        </h2>
        <Badge tone={TONES[state]}>{t.states[state]}</Badge>
      </div>

      <p className="text-muted">
        {session?.error_code ? codeText(messages, session.error_code) : t.help[state]}
      </p>
      {session && (
        <p className="text-small text-muted">
          {t.instrument} <span className="font-medium text-fg">{session.symbol}</span>
        </p>
      )}
      {!session && finished?.stop_reason && (
        <p className="text-small text-muted">
          {t.lastStop} {codeText(messages, finished.stop_reason)}
        </p>
      )}
      {waiting && <Alert tone="info">{t.waitingEngine}</Alert>}
      {failure && <Alert tone="error">{errorMessage(messages, failure)}</Alert>}

      {session === null ? (
        <>
          <Action
            icon={CirclePlay}
            label={asset ? `${t.start} · ${asset.name}` : t.start}
            variant="accent"
            onClick={start}
            pending={pending === "start"}
            disabled={!canTrade}
          />
          {blocked && (
            <p className="flex items-start gap-2 text-small text-muted">
              <Lock size={14} strokeWidth={1.5} aria-hidden className="mt-0.5 shrink-0" />
              {blocked}
            </p>
          )}
        </>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          {state === "paused" ? (
            <Action icon={CirclePlay} label={t.resume} variant="accent" onClick={() => command("resume")} pending={pending === "resume"} disabled={waiting} />
          ) : (
            <Action icon={CirclePause} label={t.pause} onClick={() => command("pause")} pending={pending === "pause"} disabled={!canPause || waiting} />
          )}
          <Action icon={CircleStop} label={t.stop} onClick={() => command("stop")} pending={pending === "stop"} disabled={!canStop || waiting} />
          <div className="col-span-2">
            <Action icon={Octagon} label={t.emergency} variant="danger" onClick={() => setConfirming(true)} pending={pending === "emergency"} disabled={session.command === "emergency"} />
          </div>
        </div>
      )}

      <Dialog open={confirming} onClose={() => setConfirming(false)} title={t.emergencyTitle} closeLabel={messages.trading.close}>
        <div className="flex flex-col gap-5">
          <p>{hasPositions ? t.emergencyBody : t.emergencyBodyEmpty}</p>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button size="lg" onClick={() => setConfirming(false)}>
              {messages.trading.cancel}
            </Button>
            <Button
              size="lg"
              variant="danger"
              onClick={() => {
                setConfirming(false);
                void command("emergency");
              }}
            >
              {t.emergencyConfirm}
            </Button>
          </div>
        </div>
      </Dialog>
    </Card>
  );
}
