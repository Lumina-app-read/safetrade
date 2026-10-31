import { notFound } from "next/navigation";

import { AffiliatePage } from "@/components/account/affiliate-page";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function Page({ params }: PageProps<"/[locale]/affiliate">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return <AffiliatePage locale={locale} messages={getMessages(locale)} />;
}
