"use client";

import { Globe } from "lucide-react";
import { usePathname } from "next/navigation";

import { rememberLocale } from "@/i18n/client";
import { LOCALES, type Locale } from "@/i18n/config";

/** Sélecteur de langue : icône et code (un drapeau serait un emoji, interdit par la section 15). */
export function LanguageSwitch({ current, label, names }: { current: Locale; label: string; names: Record<Locale, string> }) {
  const pathname = usePathname();
  const rest = pathname.split("/").slice(2).join("/");

  return (
    <nav aria-label={label} className="flex items-center rounded-lg border border-line p-0.5">
      <Globe size={18} strokeWidth={1.5} className="mx-1 text-muted" aria-hidden />
      {LOCALES.map((locale) => (
        <a
          key={locale}
          href={`/${locale}${rest ? `/${rest}` : ""}`}
          hrefLang={locale}
          lang={locale}
          title={names[locale]}
          aria-current={locale === current ? "true" : undefined}
          onClick={() => rememberLocale(locale)}
          className="rounded-md px-2 py-1 text-label font-medium text-muted uppercase hover:text-fg aria-[current=true]:bg-accent-soft aria-[current=true]:text-accent-text"
        >
          {locale}
        </a>
      ))}
    </nav>
  );
}
