import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { AppShell } from "@/components/shell/app-shell";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function AppLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return (
    <AppShell locale={locale} messages={getMessages(locale)}>
      {children}
    </AppShell>
  );
}
