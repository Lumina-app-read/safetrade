import { notFound } from "next/navigation";

import { AdminPayments } from "@/components/account/admin-payments";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function Page({ params }: PageProps<"/[locale]/admin/payments">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return <AdminPayments locale={locale} messages={getMessages(locale)} />;
}
