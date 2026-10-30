import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import en from "@/messages/en.json";
import fr from "@/messages/fr.json";

const SRC = join(__dirname, "..");
const GLOBALS = join(SRC, "app", "globals.css");

function files(dir: string, exts: string[]): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return files(path, exts);
    return exts.some((e) => path.endsWith(e)) && !path.endsWith(".test.ts") ? [path] : [];
  });
}

function keys(obj: object, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === "object" && v !== null ? keys(v as object, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

describe("règles de design (section 15)", () => {
  const sources = files(SRC, [".ts", ".tsx", ".css"]).filter((f) => f !== GLOBALS);

  it("aucune couleur écrite en dur hors des jetons de globals.css", () => {
    const offenders = sources.filter((f) => /#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|oklch\(/.test(readFileSync(f, "utf8")));
    expect(offenders).toEqual([]);
  });

  it("aucune graisse supérieure à 500", () => {
    const pattern = /font-(semibold|bold|extrabold|black)\b|font-weight:\s*[6-9]00|font-\[[6-9]00\]/;
    const offenders = [...sources, GLOBALS].filter((f) => pattern.test(readFileSync(f, "utf8")));
    expect(offenders).toEqual([]);
  });

  it("les deux blocs du thème sombre sont identiques", () => {
    const css = readFileSync(GLOBALS, "utf8");
    const blocks = [...css.matchAll(/:root[^{]*data-theme="dark"\][^{]*\{([^}]*)\}|:root:not\([^{]*\{([^}]*)\}/g)].map(
      (m) => (m[1] ?? m[2]).replace(/\s+/g, " ").trim(),
    );
    expect(blocks).toHaveLength(2);
    expect(blocks[0]).toBe(blocks[1]);
  });
});

describe("traductions", () => {
  it("le français et l'anglais ont exactement les mêmes clés", () => {
    expect(keys(en).sort()).toEqual(keys(fr).sort());
  });
});
