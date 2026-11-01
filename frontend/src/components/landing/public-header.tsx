"use client";

import { ArrowRight, Menu, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Logo } from "@/components/brand/logo";
import { LanguageSelect } from "@/components/language-select";
import { ThemeToggle } from "@/components/theme-toggle";
import type { Locale } from "@/i18n/config";
import type { Messages } from "@/i18n/messages";
import { cn } from "@/lib/cn";

import { SECTIONS } from "./anchors";

const ctaBase =
  "inline-flex items-center justify-center gap-2 rounded-lg text-label font-medium transition-colors";

export function PublicHeader({
  locale,
  messages,
}: {
  locale: Locale;
  messages: Messages;
}) {
  const t = messages.landing.nav;
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    // Menu mobile ouvert : la page derrière ne défile plus, Échap le ferme.
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) =>
      event.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <>
      <header
        className={cn(
          "sticky top-0 z-30 border-b transition-[background-color,border-color,backdrop-filter] duration-300",
          scrolled || open
            ? "border-line bg-card/85 backdrop-blur-xl"
            : "border-transparent bg-transparent",
        )}
      >
        <div className="mx-auto flex h-16 max-w-[1200px] items-center gap-3 px-5 sm:px-6">
          <a href={`/${locale}`} aria-label={t.home} className="shrink-0">
            <Logo />
          </a>
          <nav className="mx-auto hidden items-center gap-1 xl:flex">
            {SECTIONS.map((id) => (
              <a
                key={id}
                href={`#${id}`}
                className="rounded-lg px-3 py-2 text-label font-medium text-muted transition-colors hover:text-fg"
              >
                {t[id]}
              </a>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2 xl:ml-0">
            <ThemeToggle labels={messages.theme} />
            <div className="max-[379px]:hidden">
              <LanguageSelect current={locale} labels={messages.language} />
            </div>
            <a
              href={`/${locale}/login`}
              className={cn(
                ctaBase,
                "h-10 px-3 text-fg hover:bg-page max-sm:hidden",
              )}
            >
              {t.signIn}
            </a>
            <a
              href={`/${locale}/register`}
              className={cn(
                ctaBase,
                "h-10 bg-accent px-4 text-on-accent hover:bg-accent-hover max-sm:hidden",
              )}
            >
              {t.signUp}
            </a>
            <button
              type="button"
              className="grid size-10 place-items-center rounded-lg border border-line xl:hidden"
              aria-label={open ? t.closeMenu : t.openMenu}
              aria-expanded={open}
              aria-controls="mobile-menu"
              onClick={() => setOpen((v) => !v)}
            >
              {open ? (
                <X size={20} strokeWidth={1.5} aria-hidden />
              ) : (
                <Menu size={20} strokeWidth={1.5} aria-hidden />
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Hors du header : son backdrop-filter piégerait le positionnement fixe du panneau. */}
      <div
        id="mobile-menu"
        hidden={!open}
        className="fixed inset-x-0 top-16 bottom-0 z-20 animate-fade overflow-y-auto border-t border-line bg-card xl:hidden"
      >
        <nav className="flex flex-col px-5 py-4">
          {SECTIONS.map((id, i) => (
            <a
              key={id}
              href={`#${id}`}
              onClick={() => setOpen(false)}
              style={{ animationDelay: `${i * 40}ms` }}
              className="flex h-14 animate-rise items-center justify-between border-b border-line text-h3"
            >
              {t[id]}
              <ArrowRight
                size={18}
                strokeWidth={1.5}
                aria-hidden
                className="text-muted"
              />
            </a>
          ))}
        </nav>
        <div className="flex flex-col gap-3 px-5 pt-2 pb-[max(env(safe-area-inset-bottom),24px)]">
          <div className="min-[380px]:hidden">
            <LanguageSelect current={locale} labels={messages.language} />
          </div>
          <a
            href={`/${locale}/register`}
            className={cn(
              ctaBase,
              "h-12 bg-accent text-on-accent hover:bg-accent-hover",
            )}
          >
            {t.signUp}
          </a>
          <a
            href={`/${locale}/login`}
            className={cn(ctaBase, "h-12 border border-line hover:bg-page")}
          >
            {t.signIn}
          </a>
        </div>
      </div>
    </>
  );
}
