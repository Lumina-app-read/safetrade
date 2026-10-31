import { describe, expect, it } from "vitest";

import { negotiateLocale } from "./config";
import { formatters } from "./format";
import { interpolate } from "./messages";

describe("negotiateLocale", () => {
  it.each([
    ["fr-FR,fr;q=0.9,en;q=0.8", "fr"],
    ["en-US,en;q=0.9", "en"],
    ["de-DE,de;q=0.9,en;q=0.5,fr;q=0.4", "en"],
    ["fr;q=0.2,en;q=0.8", "en"],
    ["de,es", "fr"],
    ["", "fr"],
    [null, "fr"],
    ["en;q=0,fr", "fr"],
  ])("%s → %s", (header, expected) => {
    expect(negotiateLocale(header)).toBe(expected);
  });
});

describe("interpolate", () => {
  it("remplace les variables connues et laisse les autres", () => {
    expect(interpolate("Bonjour, {name} ({n})", { name: "Clovis", n: 2 })).toBe("Bonjour, Clovis (2)");
    expect(interpolate("{missing}", {})).toBe("{missing}");
  });
});

describe("formatters", () => {
  // Les espaces fines insécables du français sont normalisées pour la comparaison.
  const plain = (s: string) => s.replace(/[  ]/g, " ");

  it("formate les montants selon la langue", () => {
    expect(plain(formatters("fr").money(10012.4))).toBe("10 012,40 $");
    expect(plain(formatters("en").money(10012.4))).toBe("$10,012.40");
  });

  it("formate les dates selon la langue et le fuseau", () => {
    const d = "2026-10-30T09:12:00Z";
    expect(formatters("fr", "UTC").date(d)).toBe("30 oct. 2026");
    expect(formatters("en", "UTC").date(d)).toBe("Oct 30, 2026");
    expect(formatters("en", "UTC").time(d)).toBe("9:12 AM");
  });
});

describe("montants dans les cartes", () => {
  // Espaces insécables de Intl rendues lisibles.
  const plain = (text: string) => text.replace(/\s/g, " ");

  it("abrège les grands montants, sans perdre le signe", () => {
    expect(plain(formatters("fr").moneyShort(99999.99))).toBe("99 999,99 $");
    expect(plain(formatters("fr").moneyShort(123456.78))).toBe("123,46 k $");
    expect(plain(formatters("en").moneyShort(123456.78))).toBe("$123.46K");
    expect(plain(formatters("fr").moneyShort(1234567.89))).toBe("1,23 M $");
    expect(plain(formatters("en").moneyShort(1234567.89))).toBe("$1.23M");
    expect(plain(formatters("en").moneyShort(-2500000))).toBe("-$2.50M");
  });

  it("garde le code d'une devise inconnue du navigateur au lieu de casser la page", () => {
    expect(plain(formatters("fr").money(12.5, "USDT"))).toBe("12,50 USDT");
    expect(plain(formatters("en").moneyShort(12.5, "eUSDT"))).toBe("12.50 eUSDT");
  });
});
