import { notFound } from "next/navigation";
import { Suspense } from "react";

import { AdminUserSheet } from "@/components/account/admin-users";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

// Identifiant dans l'adresse (?id=), lu dans le navigateur : la page reste statique.
export default async function Page({ params }: PageProps<"/[locale]/admin/users/sheet">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const messages = getMessages(locale);
  return (
    <Suspense fallback={<p className="text-muted">{messages.trading.loading}</p>}>
      <AdminUserSheet locale={locale} messages={messages} />
    </Suspense>
  );
}
