import { notFound } from "next/navigation";

import { DashboardHome } from "@/components/account/dashboard-home";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function DashboardPage({ params }: PageProps<"/[locale]/dashboard">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return <DashboardHome locale={locale} messages={getMessages(locale)} />;
}
