import {
  ArrowRight,
  BarChart3,
  Bell,
  BrainCircuit,
  Check,
  ChevronDown,
  CircleDollarSign,
  Coins,
  Gauge,
  History,
  KeyRound,
  Landmark,
  Layers,
  Link2,
  LockKeyhole,
  OctagonAlert,
  Radar,
  ShieldCheck,
  SlidersHorizontal,
  Smartphone,
  Sparkles,
  TriangleAlert,
  Waves,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";

import { Logo } from "@/components/brand/logo";
import { ImageSlot } from "@/components/ui/image-slot";
import type { Locale } from "@/i18n/config";
import { formatters } from "@/i18n/format";
import type { Messages } from "@/i18n/messages";
import { cn } from "@/lib/cn";

import { SECTIONS } from "./anchors";
import { DerivSignup } from "@/components/deriv-signup";
import { Reveal } from "./reveal";
import { TradingPreview } from "./trading-preview";

type Props = { locale: Locale; messages: Messages };
type L = Messages["landing"];

const ctaPrimary =
  "inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-accent px-6 text-label font-medium text-on-accent shadow-[0_10px_30px_-10px_var(--brand-ring)] transition-[background-color,transform] hover:bg-accent-hover active:scale-[0.98]";
const ctaSecondary =
  "inline-flex h-12 items-center justify-center gap-2 rounded-lg border border-line bg-card px-6 text-label font-medium transition-colors hover:bg-page";

function Section({ id, children, className }: { id?: string; children: ReactNode; className?: string }) {
  return (
    <section id={id} className={cn("scroll-mt-20 px-5 py-20 sm:px-6 lg:py-28", className)}>
      <div className="mx-auto max-w-[1200px]">{children}</div>
    </section>
  );
}

function Heading({ eyebrow, title, subtitle, light }: { eyebrow: string; title: string; subtitle?: string; light?: boolean }) {
  return (
    <Reveal className="mx-auto mb-12 max-w-2xl text-center lg:mb-16">
      <p className={cn("text-small font-medium tracking-[0.12em] uppercase", light ? "text-on-anthracite/60" : "text-accent-text")}>
        {eyebrow}
      </p>
      <h2 className="mt-3 text-[28px] leading-tight sm:text-[34px] lg:text-[40px]">{title}</h2>
      {subtitle && <p className={cn("mt-4 text-body sm:text-[16px]", light ? "text-on-anthracite/70" : "text-muted")}>{subtitle}</p>}
    </Reveal>
  );
}

function IconTile({ icon: Icon, className }: { icon: LucideIcon; className?: string }) {
  return (
    <span className={cn("grid size-11 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-text", className)}>
      <Icon size={20} strokeWidth={1.5} aria-hidden />
    </span>
  );
}

export function Hero({ locale, messages }: Props) {
  const t = messages.landing.hero;
  return (
    <section className="relative overflow-hidden px-5 pt-10 pb-20 sm:px-6 lg:pt-16 lg:pb-28">
      <div
        aria-hidden
        className="absolute inset-0 -z-10 bg-[linear-gradient(to_right,var(--line)_1px,transparent_1px),linear-gradient(to_bottom,var(--line)_1px,transparent_1px)] [mask-image:radial-gradient(ellipse_70%_60%_at_50%_0%,black,transparent)] bg-[size:56px_56px] opacity-60"
      />
      <div
        aria-hidden
        className="absolute -top-48 left-1/2 -z-10 size-[720px] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,var(--brand-ring),transparent_65%)] opacity-60 blur-3xl"
      />
      <div className="mx-auto grid max-w-[1200px] items-center gap-14 lg:grid-cols-[1.05fr_1fr] lg:gap-16">
        <div className="animate-rise text-center lg:text-left">
          <p className="inline-flex items-center gap-2 rounded-full border border-line bg-card/70 px-3 py-1.5 text-small font-medium backdrop-blur">
            <Sparkles size={14} strokeWidth={1.5} aria-hidden className="text-accent-text" />
            {t.eyebrow}
          </p>
          <h1 className="mt-6 text-[36px] leading-[1.1] tracking-[-0.01em] sm:text-[48px] lg:text-[56px]">{t.title}</h1>
          <p className="mx-auto mt-5 max-w-xl text-[16px] text-muted sm:text-[18px] lg:mx-0">{t.subtitle}</p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center lg:justify-start">
            <a href={`/${locale}/register`} className={ctaPrimary}>
              {t.ctaPrimary}
              <ArrowRight size={18} strokeWidth={1.5} aria-hidden />
            </a>
            <a href="#how" className={ctaSecondary}>
              {t.ctaSecondary}
            </a>
          </div>
          <ul className="mt-8 flex flex-col items-center gap-2.5 text-small text-muted sm:flex-row sm:flex-wrap sm:justify-center sm:gap-x-6 lg:justify-start">
            {[t.trust1, t.trust2, t.trust3].map((item) => (
              <li key={item} className="flex items-center gap-2">
                <ShieldCheck size={16} strokeWidth={1.5} aria-hidden className="text-gain" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="animate-rise [animation-delay:150ms]">
          <ImageSlot
            name="hero"
            alt={messages.landing.images.hero}
            priority
            fallback={<TradingPreview locale={locale} messages={messages.landing.preview} />}
          />
        </div>
      </div>
    </section>
  );
}

export function HowItWorks({ messages }: Props) {
  const t = messages.landing.how;
  const steps: Array<[LucideIcon, string, string]> = [
    [Link2, t.step1Title, t.step1Body],
    [SlidersHorizontal, t.step2Title, t.step2Body],
    [Radar, t.step3Title, t.step3Body],
    [Smartphone, t.step4Title, t.step4Body],
  ];
  return (
    <Section id="how">
      <Heading eyebrow={t.eyebrow} title={t.title} />
      <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map(([icon, title, body], i) => (
          <Reveal as="li" key={title} delay={i * 80} className="group relative rounded-2xl border border-line bg-card p-6 transition-[border-color,transform] duration-300 hover:-translate-y-1 hover:border-accent/40">
            <div className="flex items-center justify-between">
              <IconTile icon={icon} />
              <span className="text-[32px] leading-none text-line tabular-nums transition-colors group-hover:text-accent/30">
                0{i + 1}
              </span>
            </div>
            <h3 className="mt-5 text-h3 font-medium">{title}</h3>
            <p className="mt-2 text-muted">{body}</p>
          </Reveal>
        ))}
      </ol>
      <div className="mt-6 empty:hidden">
        <DerivSignup messages={messages} />
      </div>
    </Section>
  );
}

export function Markets({ messages }: Props) {
  const t = messages.landing.markets;
  const items: Array<[LucideIcon, string, string, string, boolean]> = [
    [Waves, t.synthTitle, t.synthBody, t.synthTag, true],
    [Landmark, t.goldTitle, t.goldBody, t.goldTag, false],
    [Coins, t.btcTitle, t.btcBody, t.btcTag, false],
    [Layers, t.otherTitle, t.otherBody, t.otherTag, false],
  ];
  return (
    <Section id="markets" className="bg-page">
      <Heading eyebrow={t.eyebrow} title={t.title} subtitle={t.subtitle} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {items.map(([icon, title, body, tag, featured], i) => (
          <Reveal
            key={title}
            delay={i * 80}
            className={cn(
              "flex flex-col rounded-2xl border bg-card p-6 transition-[border-color,box-shadow] duration-300 hover:shadow-[0_20px_40px_-24px_var(--brand-ring)]",
              featured ? "border-accent/50" : "border-line hover:border-accent/30",
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <IconTile icon={icon} />
              <span
                className={cn(
                  "rounded-full px-2.5 py-0.5 text-small font-medium",
                  featured ? "bg-accent text-on-accent" : "border border-line text-muted",
                )}
              >
                {tag}
              </span>
            </div>
            <h3 className="mt-5 text-h3 font-medium">{title}</h3>
            <p className="mt-2 text-muted">{body}</p>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}

export function Features({ locale, messages }: Props) {
  const t = messages.landing.features;
  const items: Array<[LucideIcon, string, string]> = [
    [BarChart3, t.f1Title, t.f1Body],
    [Gauge, t.f2Title, t.f2Body],
    [BrainCircuit, t.f3Title, t.f3Body],
    [Radar, t.f4Title, t.f4Body],
    [Bell, t.f5Title, t.f5Body],
    [History, t.f6Title, t.f6Body],
  ];
  return (
    <Section id="features">
      <Heading eyebrow={t.eyebrow} title={t.title} />
      <div className="grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
        {items.map(([icon, title, body], i) => (
          <Reveal key={title} delay={(i % 3) * 80} className="flex gap-4">
            <IconTile icon={icon} />
            <div>
              <h3 className="text-h3 font-medium">{title}</h3>
              <p className="mt-1.5 text-muted">{body}</p>
            </div>
          </Reveal>
        ))}
      </div>
      <Reveal className="mt-16">
        <ImageSlot
          name="platform"
          alt={messages.landing.images.platform}
          fallback={
            <div className="mx-auto max-w-3xl">
              <TradingPreview locale={locale} messages={messages.landing.preview} />
            </div>
          }
        />
      </Reveal>
    </Section>
  );
}

function SecurityFallback() {
  return (
    <div className="relative mx-auto grid aspect-[4/3] w-full max-w-md place-items-center">
      <div aria-hidden className="absolute inset-0 rounded-full bg-[radial-gradient(circle,var(--brand-ring),transparent_60%)] blur-2xl" />
      {[100, 76, 52].map((size, i) => (
        <span
          key={size}
          aria-hidden
          className="absolute rounded-full border border-on-anthracite/10 animate-pulse-dot"
          style={{ width: `${size}%`, aspectRatio: "1", animationDelay: `${i * 400}ms` }}
        />
      ))}
      <span className="relative grid size-24 place-items-center rounded-3xl bg-accent text-on-accent shadow-[0_0_60px_var(--brand-ring)]">
        <ShieldCheck size={44} strokeWidth={1.5} aria-hidden />
      </span>
    </div>
  );
}

export function Security({ messages }: Props) {
  const t = messages.landing.security;
  const items: Array<[LucideIcon, string, string]> = [
    [ShieldCheck, t.p1Title, t.p1Body],
    [Gauge, t.p2Title, t.p2Body],
    [OctagonAlert, t.p3Title, t.p3Body],
    [CircleDollarSign, t.p4Title, t.p4Body],
    [KeyRound, t.p5Title, t.p5Body],
    [LockKeyhole, t.p6Title, t.p6Body],
  ];
  return (
    <Section id="security" className="relative overflow-hidden bg-anthracite text-on-anthracite">
      <div className="grid items-center gap-12 lg:grid-cols-[1fr_1.1fr] lg:gap-16">
        <Reveal className="order-last lg:order-first">
          <ImageSlot name="security" alt={messages.landing.images.security} fallback={<SecurityFallback />} />
        </Reveal>
        <div>
          <Reveal>
            <p className="text-small font-medium tracking-[0.12em] text-on-anthracite/60 uppercase">{t.eyebrow}</p>
            <h2 className="mt-3 text-[28px] leading-tight sm:text-[34px] lg:text-[40px]">{t.title}</h2>
            <p className="mt-4 flex gap-2.5 text-on-anthracite/75">
              <TriangleAlert size={20} strokeWidth={1.5} aria-hidden className="mt-0.5 shrink-0 text-warn-line" />
              {t.subtitle}
            </p>
          </Reveal>
          <div className="mt-10 grid gap-x-6 gap-y-7 sm:grid-cols-2">
            {items.map(([Icon, title, body], i) => (
              <Reveal key={title} delay={(i % 2) * 80} className="flex gap-3.5">
                <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-on-anthracite/10 bg-on-anthracite/5">
                  <Icon size={18} strokeWidth={1.5} aria-hidden />
                </span>
                <div>
                  <h3 className="font-medium">{title}</h3>
                  <p className="mt-1 text-small text-on-anthracite/65">{body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </div>
    </Section>
  );
}

export function Pricing({ locale, messages }: Props) {
  const t = messages.landing.pricing;
  const money = formatters(locale).money;
  // Prix fictifs décidés (docs/decisions/q05) ; ils viendront de l'API à l'étape 4.1.
  const plans: Array<{ name: string; price: string; period: string; featured?: boolean }> = [
    { name: t.trialName, price: t.trialPrice, period: t.trialPeriod },
    { name: t.weekName, price: money(5), period: t.weekPeriod },
    { name: t.monthName, price: money(15), period: t.monthPeriod, featured: true },
    { name: t.yearName, price: money(120), period: t.yearPeriod },
  ];
  return (
    <Section id="pricing" className="bg-page">
      <Heading eyebrow={t.eyebrow} title={t.title} subtitle={t.subtitle} />
      {/* Téléphone : carrousel horizontal aimanté ; tablette et plus : grille. */}
      <div className="-mx-5 flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-smooth px-5 pt-4 pb-2 [scrollbar-width:none] sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:px-0 lg:grid-cols-4 [&::-webkit-scrollbar]:hidden">
        {plans.map((plan, i) => (
          <Reveal
            key={plan.name}
            delay={i * 80}
            className={cn(
              "relative flex w-[82%] shrink-0 snap-center flex-col rounded-2xl border bg-card p-6 transition-transform duration-300 hover:-translate-y-1 sm:w-auto",
              plan.featured ? "border-accent shadow-[0_24px_60px_-28px_var(--brand-ring)]" : "border-line",
            )}
          >
            {plan.featured && (
              <span className="absolute -top-3 left-6 rounded-full bg-accent px-3 py-1 text-small font-medium text-on-accent">
                {t.popular}
              </span>
            )}
            <h3 className="text-h3 font-medium">{plan.name}</h3>
            <p className="mt-4">
              <span className="text-[30px] font-medium tabular-nums">{plan.price}</span>{" "}
              <span className="text-muted">{plan.period}</span>
            </p>
            <ul className="mt-6 flex flex-1 flex-col gap-2.5 text-small">
              {[t.includes1, t.includes2, t.includes3].map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <Check size={16} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0 text-gain" />
                  {item}
                </li>
              ))}
            </ul>
            <a href={`/${locale}/register`} className={cn(plan.featured ? ctaPrimary : ctaSecondary, "mt-7 w-full")}>
              {t.cta}
            </a>
          </Reveal>
        ))}
      </div>
      <Reveal className="mt-8 flex flex-col items-center gap-1 text-center text-small text-muted">
        <p>{t.payment}</p>
        <p>{t.provisional}</p>
      </Reveal>
    </Section>
  );
}

export function Faq({ messages }: Props) {
  const t = messages.landing.faq;
  const items = [1, 2, 3, 4, 5, 6] as const;
  return (
    <Section id="faq">
      <Heading eyebrow={t.eyebrow} title={t.title} />
      <div className="mx-auto flex max-w-3xl flex-col gap-3">
        {items.map((n, i) => (
          <Reveal key={n} delay={i * 50}>
            {/* <details> natif : accessible au clavier et lisible sans JavaScript. */}
            <details className="group rounded-xl border border-line bg-card transition-colors open:border-accent/40">
              <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 font-medium [&::-webkit-details-marker]:hidden">
                {t[`q${n}`]}
                <ChevronDown
                  size={20}
                  strokeWidth={1.5}
                  aria-hidden
                  className="shrink-0 text-muted transition-transform duration-300 group-open:rotate-180 group-open:text-accent-text"
                />
              </summary>
              <p className="animate-fade px-5 pb-5 text-muted">{t[`a${n}`]}</p>
            </details>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}

export function FinalCta({ locale, messages }: Props) {
  const t = messages.landing.cta;
  return (
    <section className="px-5 pb-20 sm:px-6 lg:pb-28">
      <Reveal className="relative mx-auto max-w-[1200px] overflow-hidden rounded-3xl bg-anthracite px-6 py-14 text-center text-on-anthracite sm:px-12 lg:py-20">
        <div aria-hidden className="absolute -top-32 left-1/2 size-[520px] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,var(--brand-ring),transparent_65%)] blur-2xl" />
        <h2 className="relative text-[28px] leading-tight sm:text-[36px]">{t.title}</h2>
        <p className="relative mx-auto mt-4 max-w-xl text-on-anthracite/75">{t.body}</p>
        <a href={`/${locale}/register`} className={cn(ctaPrimary, "relative mt-8 w-full sm:w-auto")}>
          {t.button}
          <ArrowRight size={18} strokeWidth={1.5} aria-hidden />
        </a>
      </Reveal>
    </section>
  );
}

export function Footer({ locale, messages }: Props) {
  const t: L["footer"] = messages.landing.footer;
  const nav = messages.landing.nav;
  return (
    <footer className="border-t border-line bg-card px-5 pt-14 pb-[max(env(safe-area-inset-bottom),32px)] sm:px-6">
      <div className="mx-auto max-w-[1200px]">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.5fr_1fr_1fr]">
          <div>
            <a href={`/${locale}`} aria-label={nav.home}>
              <Logo />
            </a>
            <p className="mt-4 max-w-sm text-muted">{t.tagline}</p>
          </div>
          <div>
            <h2 className="text-small font-medium tracking-[0.08em] text-muted uppercase">{t.product}</h2>
            <ul className="mt-4 flex flex-col gap-2.5">
              {SECTIONS.map((id) => (
                <li key={id}>
                  <a href={`#${id}`} className="hover:text-accent-text">
                    {nav[id]}
                  </a>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h2 className="text-small font-medium tracking-[0.08em] text-muted uppercase">{t.legal}</h2>
            {/* Pages légales publiées à l'étape 8.3, après avis juridique. */}
            <ul className="mt-4 flex flex-col gap-2.5 text-muted">
              {[t.legalNotice, t.terms, t.privacy, t.riskWarning].map((item) => (
                <li key={item} className="flex flex-wrap items-center gap-x-2">
                  {item}
                  <span className="text-small">· {t.soon}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <p className="mt-12 border-t border-line pt-6 text-small text-muted">{t.disclaimer}</p>
        <p className="mt-4 text-small text-muted">{t.rights}</p>
      </div>
    </footer>
  );
}
