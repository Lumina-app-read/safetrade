import { INTL_LOCALE, type Locale } from "./config";

/**
 * Formats dépendant de la langue (section 15) : nombres, montants, dates.
 * Les montants affichent le code de devise (« 10 012,40 USD »), plus lisible
 * que le symbole « $US » en français.
 */
export function formatters(locale: Locale, timeZone?: string) {
  const intl = INTL_LOCALE[locale];
  return {
    number: (value: number) => new Intl.NumberFormat(intl).format(value),
    /** 0.0084 → « +0,84 % » (signed) ou « 0,84 % ». */
    percent: (value: number, digits = 0, signed = false) =>
      new Intl.NumberFormat(intl, {
        style: "percent",
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
        signDisplay: signed ? "exceptZero" : "auto",
      }).format(value),
    money: (value: number, currency = "USD") =>
      new Intl.NumberFormat(intl, { style: "currency", currency, currencyDisplay: "code" }).format(value),
    date: (value: Date | string) => new Intl.DateTimeFormat(intl, { dateStyle: "medium", timeZone }).format(new Date(value)),
    /** « il y a 5 minutes », « hier »... par rapport à maintenant. */
    relative: (value: Date | string, now: Date = new Date()) => {
      const seconds = (new Date(value).getTime() - now.getTime()) / 1000;
      const rtf = new Intl.RelativeTimeFormat(intl, { numeric: "auto" });
      const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
        ["day", 86400],
        ["hour", 3600],
        ["minute", 60],
      ];
      for (const [unit, size] of units) {
        if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
      }
      return rtf.format(0, "minute");
    },
    time: (value: Date | string) => new Intl.DateTimeFormat(intl, { timeStyle: "short", timeZone }).format(new Date(value)),
  };
}
