import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { getMessages } from "@/i18n/messages";

import { errorMessage } from "./api";

const BACKEND_APP = join(__dirname, "..", "..", "..", "backend", "app");
const SRC = join(__dirname, "..");

function walk(dir: string, ext: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path, ext) : path.endsWith(ext) ? [path] : [];
  });
}

describe("codes d'erreur de l'API", () => {
  const backendCodes = new Set(
    walk(BACKEND_APP, ".py").flatMap((f) =>
      [...readFileSync(f, "utf8").matchAll(/ApiError\(\s*\d+,\s*"([a-z_.]+)"/g)].map((m) => m[1]),
    ),
  );
  backendCodes.add("validation.invalid");
  backendCodes.add("network.unavailable");

  it("trouve les codes du backend", () => {
    expect(backendCodes.size).toBeGreaterThan(5);
  });

  it.each(["fr", "en"] as const)("chaque code a une traduction dédiée (%s)", (locale) => {
    const messages = getMessages(locale);
    const missing = [...backendCodes].filter((code) => !(code.replace(/\./g, "_") in messages.errors));
    expect(missing).toEqual([]);
  });

  it("indique le délai d'attente en minutes", () => {
    const text = errorMessage(getMessages("fr"), { code: "auth.too_many_attempts", retryAfter: 900 });
    expect(text).toBe("Trop de tentatives. Réessayez dans 15 minutes.");
  });

  it("repli sur un message générique pour un code inconnu", () => {
    expect(errorMessage(getMessages("en"), { code: "something.new" })).toBe(getMessages("en").errors.unknown);
  });
});

describe("emojis (section 15)", () => {
  it("un seul emoji dans l'interface : la salutation du tableau de bord", () => {
    // ©, ® et ™ sont des pictogrammes Unicode mais s'affichent comme du texte.
    const emoji = /(?![©®™])\p{Extended_Pictographic}/u;
    const files = [...walk(SRC, ".tsx"), ...walk(join(SRC, "messages"), ".json")].filter((f) =>
      emoji.test(readFileSync(f, "utf8")),
    );
    expect(files.map((f) => f.replace(SRC, "").replace(/\\/g, "/"))).toEqual(["/components/account/dashboard-greeting.tsx"]);
  });
});
