import { notFound } from "next/navigation";

import { HistoryPage } from "@/components/trading/history-page";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function Page({ params }: PageProps<"/[locale]/history">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return <HistoryPage locale={locale} messages={getMessages(locale)} />;
}
