import { notFound } from "next/navigation";

import { AdminSettings } from "@/components/account/admin-settings";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function Page({ params }: PageProps<"/[locale]/admin/settings">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return <AdminSettings messages={getMessages(locale)} />;
}
