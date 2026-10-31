import { notFound } from "next/navigation";

import { SubscriptionPage } from "@/components/account/subscription-page";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function Page({ params }: PageProps<"/[locale]/subscription">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return <SubscriptionPage locale={locale} messages={getMessages(locale)} />;
}
