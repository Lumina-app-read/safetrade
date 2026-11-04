import { notFound } from "next/navigation";

import { AdminTrading } from "@/components/account/admin-trading";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function Page({ params }: PageProps<"/[locale]/admin/trading">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return <AdminTrading locale={locale} messages={getMessages(locale)} />;
}
