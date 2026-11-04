import { notFound } from "next/navigation";

import { AdminAudit } from "@/components/account/admin-audit";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function Page({ params }: PageProps<"/[locale]/admin/audit">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return <AdminAudit locale={locale} messages={getMessages(locale)} />;
}
