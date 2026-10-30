/** Description courte d'un appareil d'après son User-Agent (liste des sessions). */
export type DeviceKind = "mobile" | "tablet" | "desktop";

const SYSTEMS: Array<[RegExp, string, DeviceKind]> = [
  [/iPad/, "iPad", "tablet"],
  [/iPhone/, "iPhone", "mobile"],
  [/Android.*Mobile/, "Android", "mobile"],
  [/Android/, "Android", "tablet"],
  [/Windows/, "Windows", "desktop"],
  [/Mac OS X|Macintosh/, "macOS", "desktop"],
  [/CrOS/, "ChromeOS", "desktop"],
  [/Linux/, "Linux", "desktop"],
];

// Ordre important : Edge et Opera contiennent aussi « Chrome », Chrome contient « Safari ».
const BROWSERS: Array<[RegExp, string]> = [
  [/Edg\//, "Edge"],
  [/OPR\/|Opera/, "Opera"],
  [/SamsungBrowser/, "Samsung Internet"],
  [/Firefox\/|FxiOS/, "Firefox"],
  [/Chrome\/|CriOS/, "Chrome"],
  [/Safari\//, "Safari"],
];

export function describeDevice(userAgent: string | null | undefined): { kind: DeviceKind; label: string | null } {
  if (!userAgent) return { kind: "desktop", label: null };
  const system = SYSTEMS.find(([re]) => re.test(userAgent));
  const browser = BROWSERS.find(([re]) => re.test(userAgent))?.[1];
  const parts = [browser, system?.[1]].filter(Boolean);
  return { kind: system?.[2] ?? "desktop", label: parts.length ? parts.join(" · ") : null };
}
