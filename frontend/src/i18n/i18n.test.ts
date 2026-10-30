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
    expect(plain(formatters("fr").money(10012.4))).toBe("10 012,40 USD");
    expect(plain(formatters("en").money(10012.4))).toBe("USD 10,012.40");
  });

  it("formate les dates selon la langue et le fuseau", () => {
    const d = "2026-10-30T09:12:00Z";
    expect(formatters("fr", "UTC").date(d)).toBe("30 oct. 2026");
    expect(formatters("en", "UTC").date(d)).toBe("Oct 30, 2026");
    expect(formatters("en", "UTC").time(d)).toBe("9:12 AM");
  });
});
