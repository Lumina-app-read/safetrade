import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { getMessages } from "@/i18n/messages";

import { codeText, priceDecimals, usage } from "./labels";

const TRADING = join(__dirname, "..", "..", "..", "..", "backend", "app");

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return path.endsWith(".py") ? [path] : [];
  });
}

describe.each(["fr", "en"] as const)("libellés du moteur (%s)", (locale) => {
  const messages = getMessages(locale);

  it("traduit tous les motifs émis par le backend", () => {
    const files = [...sources(join(TRADING, "trading")), join(TRADING, "market", "quality.py")];
    const text = files.map((f) => readFileSync(f, "utf8")).join("\n");
    const codes = [...text.matchAll(/"((?:risk|market|strategy|order|reconcile|position)\.[a-z_]+)"/g)].map((m) => m[1]);
    const statuses = ["stale", "closed", "suspended", "unavailable"].map((s) => `market.${s}`);
    const missing = [...new Set([...codes, ...statuses])].filter((code) => codeText(messages, code) === messages.trading.codes.unknown);
    expect(missing).toEqual([]);
  });

  it("explique un refus de Deriv par son préfixe", () => {
    expect(codeText(messages, "order.refused_InvalidOfferings")).toBe(messages.trading.codes.order_refused);
    expect(codeText(messages, "order.proposal_RequestTimeoutError")).toBe(messages.trading.codes.order_proposal);
    expect(codeText(messages, "inconnu.xyz")).toBe(messages.trading.codes.unknown);
    expect(codeText(messages, null)).toBe("");
  });
});

describe("calculs d'affichage", () => {
  it("déduit les décimales du pas de cotation", () => {
    expect(priceDecimals(0.01)).toBe(2);
    expect(priceDecimals(0.001)).toBe(3);
    expect(priceDecimals(1)).toBe(0);
  });

  it("borne la consommation d'une limite", () => {
    expect(usage(0, 10)).toBe(0);
    expect(usage(5, 10)).toBe(0.5);
    expect(usage(20, 10)).toBe(1);
    expect(usage(1, 0)).toBe(0);
  });
});
