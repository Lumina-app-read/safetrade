import { notFound } from "next/navigation";

import { ComingSoon } from "@/components/shell/coming-soon";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function Page({ params }: PageProps<"/[locale]/subscription">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const messages = getMessages(locale);
  return <ComingSoon locale={locale} messages={messages} title={messages.nav.subscription} body={messages.soon.subscriptionBody} />;
}
