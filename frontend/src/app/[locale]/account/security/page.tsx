import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { SecurityPanel } from "@/components/account/security-panel";
import { TopBar } from "@/components/top-bar";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export async function generateMetadata({ params }: PageProps<"/[locale]/account/security">): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale) ? { title: `${getMessages(locale).security.title} · SafeTrade` } : {};
}

export default async function SecurityPage({ params }: PageProps<"/[locale]/account/security">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const messages = getMessages(locale);
  const t = messages.security;
  return (
    <>
      <TopBar locale={locale} messages={messages} />
      <main className="mx-auto max-w-[1200px] pt-6 pb-16 sm:px-6 sm:pt-8">
        <div className="px-5 sm:px-0">
          <a
            href={`/${locale}/dashboard`}
            className="inline-flex h-10 items-center gap-1.5 text-label font-medium text-muted hover:text-fg"
          >
            <ArrowLeft size={16} strokeWidth={1.5} aria-hidden />
            {t.back}
          </a>
          <h1 className="mt-2 text-h1">{t.title}</h1>
          <p className="mt-1 mb-6 text-muted">{t.subtitle}</p>
        </div>
        <SecurityPanel locale={locale} messages={messages} />
      </main>
    </>
  );
}
