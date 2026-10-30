import { notFound } from "next/navigation";

import { AdminOverview } from "@/components/account/admin-overview";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function AdminPage({ params }: PageProps<"/[locale]/admin">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return <AdminOverview locale={locale} messages={getMessages(locale)} />;
}
