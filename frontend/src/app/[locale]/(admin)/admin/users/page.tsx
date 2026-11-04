import { notFound } from "next/navigation";

import { AdminUsers } from "@/components/account/admin-users";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function Page({ params }: PageProps<"/[locale]/admin/users">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return <AdminUsers locale={locale} messages={getMessages(locale)} />;
}
