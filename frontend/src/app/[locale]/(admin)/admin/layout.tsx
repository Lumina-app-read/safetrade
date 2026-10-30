import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { AdminShell } from "@/components/shell/admin-shell";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function AdminLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return (
    <AdminShell locale={locale} messages={getMessages(locale)}>
      {children}
    </AdminShell>
  );
}
