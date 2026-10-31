import { notFound } from "next/navigation";

import { TradingPage } from "@/components/trading/trading-page";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function Page({ params }: PageProps<"/[locale]/trading">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return <TradingPage locale={locale} messages={getMessages(locale)} />;
}
