import { notFound } from "next/navigation";

import { TopBar } from "@/components/top-bar";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

// Page d'accueil provisoire : remplacée par la page de présentation publique.
export default async function Home({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const m = getMessages(locale);
  return (
    <>
      <TopBar locale={locale} messages={m} />
      <main className="mx-auto max-w-[1200px] px-4 pt-8 sm:px-6">
        <h1 className="text-h1">SafeTrade</h1>
        <p className="text-small text-muted">{m.home.status}</p>
      </main>
    </>
  );
}
