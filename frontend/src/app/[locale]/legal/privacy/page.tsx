import { notFound } from "next/navigation";

import { PublicHeader } from "@/components/landing/public-header";
import { Footer } from "@/components/landing/sections";
import { LegalPage } from "@/components/site/legal-page";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function Page({ params }: PageProps<"/[locale]/legal/privacy">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const messages = getMessages(locale);
  return (
    <div className="bg-card">
      <PublicHeader locale={locale} messages={messages} />
      <LegalPage kind="privacy" locale={locale} messages={messages} />
      <Footer locale={locale} messages={messages} />
    </div>
  );
}
