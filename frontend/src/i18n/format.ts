import { INTL_LOCALE, type Locale } from "./config";

const COMPACT_FROM = 100_000;

/**
 * Montant avec le symbole court de la devise (« 10 012,40 $ »), plus étroit que son code.
 * Une devise que le navigateur ne connaît pas (USDT, USDC...) garde son code : un format
 * refusé ne doit jamais casser la page.
 */
function formatMoney(intl: string, value: number, currency: string, options: Intl.NumberFormatOptions = {}): string {
  try {
    return new Intl.NumberFormat(intl, { style: "currency", currency, currencyDisplay: "narrowSymbol", ...options }).format(value);
  } catch {
    return `${new Intl.NumberFormat(intl, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)} ${currency}`;
  }
}

/**
 * Formats dépendant de la langue (section 15) : nombres, montants, dates.
 */
/** Fuseau du navigateur : la journée de trading se calcule dans le fuseau du client. */
export function browserTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

export function formatters(locale: Locale, timeZone?: string) {
  const intl = INTL_LOCALE[locale];
  return {
    number: (value: number) => new Intl.NumberFormat(intl).format(value),
    /** Cours d'un actif, avec le nombre de décimales de sa cotation. */
    price: (value: number, digits: number) =>
      new Intl.NumberFormat(intl, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value),
    dateTime: (value: Date | string) =>
      new Intl.DateTimeFormat(intl, { dateStyle: "short", timeStyle: "short", timeZone }).format(new Date(value)),
    /** 0.0084 → « +0,84 % » (signed) ou « 0,84 % ». */
    percent: (value: number, digits = 0, signed = false) =>
      new Intl.NumberFormat(intl, {
        style: "percent",
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
        signDisplay: signed ? "exceptZero" : "auto",
      }).format(value),
    money: (value: number, currency = "USD") => formatMoney(intl, value, currency),
    /** Pour les cartes étroites : forme abrégée dès 100 000 (« 123,46 k $ », « 1,23 M $ »). */
    moneyShort: (value: number, currency = "USD") =>
      Math.abs(value) < COMPACT_FROM
        ? formatMoney(intl, value, currency)
        : formatMoney(intl, value, currency, { notation: "compact", maximumFractionDigits: 2 }),
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
