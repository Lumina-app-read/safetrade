import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { SecurityPanel } from "@/components/account/security-panel";
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
      <h1 className="text-h1">{t.title}</h1>
      <p className="mt-1 mb-6 text-muted">{t.subtitle}</p>
      <SecurityPanel locale={locale} messages={messages} />
    </>
  );
}
