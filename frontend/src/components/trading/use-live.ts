"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";

import type { Asset, Tick } from "./types";

type Failure = { code: string; status: number; retryAfter?: number };
type Polled<T> = { data: T | null; error: Failure | null; loading: boolean };

const STREAM_GRACE_MS = 5000;
const STREAM_RETRY_MS = 5000;
const PRICE_FLUSH_MS = 500;

/**
 * Lecture périodique de l'API. La dernière réponse reste affichée pendant une panne, `error`
 * signale qu'elle n'est plus à jour. `every` à 0 : une seule lecture. Page cachée : pause.
 */
export function usePolled<T>(path: string | null, every: number) {
  const [state, setState] = useState<Polled<T>>({ data: null, error: null, loading: true });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (!path) return;
    let stopped = false;
    let busy = false;

    async function read() {
      if (busy || document.hidden) return;
      busy = true;
      const result = await api<T>(path as string);
      busy = false;
      if (stopped) return;
      // Session expirée : le contrôle d'accès de la page renvoie vers la connexion.
      if (!result.ok && result.status === 401) window.location.reload();
      setState((current) =>
        result.ok
          ? { data: result.data, error: null, loading: false }
          : { data: current.data, error: result, loading: false },
      );
    }

    void read();
    const timer = every > 0 ? setInterval(() => void read(), every) : undefined;
    const onVisible = () => void read();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      stopped = true;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [path, every, version]);

  const reload = useCallback(() => setVersion((value) => value + 1), []);
  return { ...state, reload };
}

/** Heure courante rafraîchie : pour les durées, sans lire l'horloge pendant le rendu. */
export function useNow(every = 1000): number {
  const [now, setNow] = useState(0);
  useEffect(() => {
    const update = () => setNow(Date.now());
    const first = setTimeout(update, 0);
    const timer = setInterval(update, every);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [every]);
  return now;
}

export type StreamState = "connecting" | "live" | "lost";
type TickListener = (tick: Tick) => void;
type GapListener = (symbol: string) => void;

/**
 * Prix en direct par SSE. Le serveur ferme le flux toutes les 5 minutes et le navigateur se
 * reconnecte : une coupure n'est annoncée que si elle dure, pour éviter un faux signal.
 */
export function useMarket(symbols: string[] | null) {
  const assets = usePolled<{ assets: Asset[] }>("/market/assets", 15000);
  const [prices, setPrices] = useState<Record<string, Tick>>({});
  const [stream, setStream] = useState<StreamState>("connecting");
  const tickListeners = useRef(new Set<TickListener>());
  const gapListeners = useRef(new Set<GapListener>());
  const watched = symbols?.join(",") ?? null;

  useEffect(() => {
    // Les actifs affichés ne sont pas encore connus : rien à écouter.
    if (watched === null) return;
    const query = watched
      .split(",")
      .filter(Boolean)
      .map((symbol) => `symbols=${encodeURIComponent(symbol)}`)
      .join("&");
    let source: EventSource | null = null;
    let grace: ReturnType<typeof setTimeout> | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let pending: Record<string, Tick> = {};

    function lost() {
      clearTimeout(grace);
      grace = setTimeout(() => setStream("lost"), STREAM_GRACE_MS);
    }

    function open() {
      source = new EventSource(`/api/market/stream?${query}`);
      source.onopen = () => {
        clearTimeout(grace);
        setStream("live");
      };
      source.onerror = () => {
        lost();
        // Refus définitif (session, limite de flux) : le navigateur n'insiste pas seul.
        if (source?.readyState === EventSource.CLOSED) {
          source.close();
          retry = setTimeout(open, STREAM_RETRY_MS);
        }
      };
      source.addEventListener("tick", (event) => {
        const tick = JSON.parse((event as MessageEvent<string>).data) as Tick;
        pending[tick.symbol] = tick;
        tickListeners.current.forEach((listen) => listen(tick));
      });
      source.addEventListener("gap", (event) => {
        const { symbol } = JSON.parse((event as MessageEvent<string>).data) as { symbol: string };
        gapListeners.current.forEach((listen) => listen(symbol));
      });
    }

    open();
    // Affichage regroupé : le graphique reçoit chaque tick, le reste de la page non.
    const flush = setInterval(() => {
      if (Object.keys(pending).length === 0) return;
      const batch = pending;
      pending = {};
      setPrices((current) => ({ ...current, ...batch }));
    }, PRICE_FLUSH_MS);

    return () => {
      clearInterval(flush);
      clearTimeout(grace);
      clearTimeout(retry);
      source?.close();
    };
  }, [watched]);

  const onTick = useCallback((listen: TickListener) => {
    const listeners = tickListeners.current;
    listeners.add(listen);
    return () => void listeners.delete(listen);
  }, []);

  const onGap = useCallback((listen: GapListener) => {
    const listeners = gapListeners.current;
    listeners.add(listen);
    return () => void listeners.delete(listen);
  }, []);

  return {
    assets: assets.data?.assets ?? [],
    loading: assets.loading,
    error: assets.error,
    prices,
    stream,
    onTick,
    onGap,
  };
}

export type Market = ReturnType<typeof useMarket>;
