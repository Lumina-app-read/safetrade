// Contrôle des traductions, exécuté avant chaque build (npm run build) et en CI.
// Échoue si une langue n'a pas exactement les clés du français, si une valeur
// est vide, ou si les variables « {nom} » diffèrent d'une langue à l'autre.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const DIR = join(import.meta.dirname, "..", "src", "messages");
const REFERENCE = "fr";

function flatten(obj, prefix = "") {
  return Object.entries(obj).flatMap(([key, value]) =>
    value !== null && typeof value === "object" ? flatten(value, `${prefix}${key}.`) : [[`${prefix}${key}`, value]],
  );
}

const variables = (text) => [...String(text).matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");

const catalogs = Object.fromEntries(
  readdirSync(DIR)
    .filter((file) => file.endsWith(".json"))
    .map((file) => [file.replace(/\.json$/, ""), new Map(flatten(JSON.parse(readFileSync(join(DIR, file), "utf8"))))]),
);

const reference = catalogs[REFERENCE];
const errors = [];
for (const [locale, entries] of Object.entries(catalogs)) {
  for (const key of reference.keys()) if (!entries.has(key)) errors.push(`${locale} : clé manquante « ${key} »`);
  for (const [key, value] of entries) {
    if (!reference.has(key)) errors.push(`${locale} : clé inconnue du français « ${key} »`);
    else if (typeof value !== "string" || value.trim() === "") errors.push(`${locale} : valeur vide « ${key} »`);
    else if (variables(value) !== variables(reference.get(key))) errors.push(`${locale} : variables différentes « ${key} »`);
  }
}

if (errors.length > 0) {
  console.error(`Traductions incomplètes (${errors.length}) :\n- ${errors.join("\n- ")}`);
  process.exit(1);
}
console.log(`Traductions complètes : ${Object.keys(catalogs).join(", ")} (${reference.size} clés).`);
