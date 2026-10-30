"use client";

import { Check, ChevronDown } from "lucide-react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { rememberLocale } from "@/i18n/client";
import { LOCALES, type Locale } from "@/i18n/config";
import { cn } from "@/lib/cn";

// Drapeaux en SVG (public/flags) : un drapeau-emoji est interdit par la section 15.
const FLAGS: Record<Locale, string> = { fr: "/flags/fr.svg", en: "/flags/gb.svg" };

function Flag({ locale }: { locale: Locale }) {
  return (
    <Image
      src={FLAGS[locale]}
      alt=""
      width={20}
      height={14}
      unoptimized
      className="h-3.5 w-5 shrink-0 rounded-[3px] object-cover ring-1 ring-line"
    />
  );
}

/**
 * Sélecteur de langue déroulant : le bouton affiche le drapeau et le code (FR, EN),
 * la liste le drapeau et le nom de chaque langue dans sa propre langue.
 */
export function LanguageSelect({
  current,
  labels,
}: {
  current: Locale;
  labels: { menu: string; names: Record<Locale, string> };
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const items = useRef<Array<HTMLAnchorElement | null>>([]);
  const pathname = usePathname();
  const rest = pathname.split("/").slice(2).join("/");

  useEffect(() => {
    if (!open) return;
    items.current[LOCALES.indexOf(current)]?.focus();
    const close = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open, current]);

  function onKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      setOpen(false);
      root.current?.querySelector("button")?.focus();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const index = items.current.findIndex((el) => el === document.activeElement);
      const step = event.key === "ArrowDown" ? 1 : -1;
      items.current[(index + step + LOCALES.length) % LOCALES.length]?.focus();
    }
  }

  return (
    <div ref={root} className="relative" onKeyDown={onKeyDown}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${labels.menu} (${labels.names[current]})`}
        onClick={() => setOpen((v) => !v)}
        className="flex h-10 items-center gap-2 rounded-lg border border-line pr-2 pl-2.5 text-label font-medium transition-colors hover:border-muted/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent aria-expanded:border-accent"
      >
        <Flag locale={current} />
        <span className="uppercase">{current}</span>
        <ChevronDown
          size={16}
          strokeWidth={1.5}
          aria-hidden
          className={cn("text-muted transition-transform duration-200", open && "rotate-180")}
        />
      </button>
      <div
        role="menu"
        aria-label={labels.menu}
        hidden={!open}
        className="absolute right-0 z-20 mt-2 w-44 origin-top-right animate-rise rounded-xl border border-line bg-card p-1.5 shadow-[0_12px_32px_-12px_var(--brand-ring)]"
      >
        {LOCALES.map((locale, index) => (
          <a
            key={locale}
            ref={(el) => {
              items.current[index] = el;
            }}
            role="menuitemradio"
            aria-checked={locale === current}
            href={`/${locale}${rest ? `/${rest}` : ""}`}
            hrefLang={locale}
            lang={locale}
            onClick={() => rememberLocale(locale)}
            className="flex h-11 items-center gap-3 rounded-lg px-2.5 text-body outline-none hover:bg-page focus-visible:bg-page aria-checked:font-medium"
          >
            <Flag locale={locale} />
            <span className="flex-1">{labels.names[locale]}</span>
            {locale === current && <Check size={16} strokeWidth={1.5} aria-hidden className="text-accent-text" />}
          </a>
        ))}
      </div>
    </div>
  );
}
