import { describe, expect, it } from "vitest";

import { formatters } from "@/i18n/format";

import { describeDevice } from "./device";

describe("describeDevice", () => {
  it.each([
    [
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
      "mobile",
      "Safari · iPhone",
    ],
    [
      "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36",
      "mobile",
      "Chrome · Android",
    ],
    [
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36 Edg/126.0",
      "desktop",
      "Edge · Windows",
    ],
    ["Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:127.0) Gecko/20100101 Firefox/127.0", "desktop", "Firefox · macOS"],
    ["curl/8.0", "desktop", null],
  ])("%s", (ua, kind, label) => {
    expect(describeDevice(ua)).toEqual({ kind, label });
  });

  it("gère l'absence de User-Agent", () => {
    expect(describeDevice(null)).toEqual({ kind: "desktop", label: null });
  });
});

describe("formatters.relative", () => {
  const now = new Date("2026-10-30T12:00:00Z");
  it("formate selon la langue", () => {
    expect(formatters("fr").relative("2026-10-30T11:55:00Z", now)).toBe("il y a 5 minutes");
    expect(formatters("en").relative("2026-10-29T12:00:00Z", now)).toBe("yesterday");
    expect(formatters("en").relative("2026-10-30T11:59:50Z", now)).toBe("this minute");
  });
});
