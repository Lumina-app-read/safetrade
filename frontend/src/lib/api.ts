/**
 * Appels à l'API SafeTrade, servie sous /api sur la même origine (cookie de session HttpOnly).
 * Le backend renvoie des codes d'erreur ; ils sont traduits par errorMessage().
 */

import { interpolate, type Messages } from "@/i18n/messages";

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; code: string; status: number; retryAfter?: number; fields?: string[] };

export async function api<T>(path: string, init?: { method?: string; body?: unknown }): Promise<ApiResult<T>> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method: init?.method ?? (init?.body === undefined ? "GET" : "POST"),
      headers: init?.body === undefined ? undefined : { "Content-Type": "application/json" },
      body: init?.body === undefined ? undefined : JSON.stringify(init.body),
      credentials: "same-origin",
    });
  } catch {
    return { ok: false, code: "network.unavailable", status: 0 };
  }
  if (response.status === 204) return { ok: true, data: undefined as T };
  const payload = (await response.json().catch(() => ({}))) as { error?: string; fields?: string[] } & T;
  if (response.ok) return { ok: true, data: payload };
  const retry = Number(response.headers.get("retry-after"));
  return {
    ok: false,
    code: payload.error ?? (response.status >= 500 ? "network.unavailable" : "unknown"),
    status: response.status,
    retryAfter: Number.isFinite(retry) && retry > 0 ? retry : undefined,
    fields: payload.fields,
  };
}

/** Code d'erreur de l'API (« auth.too_many_attempts ») vers le texte traduit. */
export function errorMessage(messages: Messages, error: { code: string; retryAfter?: number }): string {
  const key = error.code.replace(/\./g, "_") as keyof Messages["errors"];
  const text = messages.errors[key] ?? messages.errors.unknown;
  return interpolate(text, { minutes: Math.max(1, Math.ceil((error.retryAfter ?? 60) / 60)) });
}
