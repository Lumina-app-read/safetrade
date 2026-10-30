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
    time: (value: Date | string) => new Intl.DateTimeFormat(intl, { timeStyle: "short", timeZone }).format(new Date(value)),
  };
}
