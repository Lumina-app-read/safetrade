import { notFound } from "next/navigation";

import { AdminPlans } from "@/components/account/admin-plans";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function Page({ params }: PageProps<"/[locale]/admin/subscriptions">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return <AdminPlans locale={locale} messages={getMessages(locale)} />;
}
