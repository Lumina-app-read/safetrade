import { notFound } from "next/navigation";

import { DashboardGreeting } from "@/components/account/dashboard-greeting";
import { TopBar } from "@/components/top-bar";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export default async function DashboardPage({ params }: PageProps<"/[locale]/dashboard">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const messages = getMessages(locale);
  return (
    <>
      <TopBar locale={locale} messages={messages} current="dashboard" />
      <main className="mx-auto max-w-[1200px] px-5 pt-8 sm:px-6">
        <DashboardGreeting locale={locale} messages={messages} />
      </main>
    </>
  );
}
