"use client";

import { Card, SectionTitle } from "@/components/ui/card";
import type { Locale } from "@/i18n/config";
import type { Messages } from "@/i18n/messages";

import { HistoryPanel } from "./history-panel";
import { JournalPanel } from "./journal-panel";
import type { Asset } from "./types";
import { usePolled } from "./use-live";

/** Historique complet : transactions clôturées et journal des décisions du moteur. */
export function HistoryPage({ locale, messages }: { locale: Locale; messages: Messages }) {
  const assets = usePolled<{ assets: Asset[] }>("/market/assets", 0);
  return (
    <div className="flex flex-col">
      <h1 className="text-h1">{messages.nav.history}</h1>
      <SectionTitle>{messages.trading.tabs.history}</SectionTitle>
      <Card className="p-4 sm:p-5">
        <HistoryPanel assets={assets.data?.assets ?? []} locale={locale} messages={messages} />
      </Card>
      <SectionTitle>{messages.trading.tabs.journal}</SectionTitle>
      <Card className="p-4 sm:p-5">
        <JournalPanel locale={locale} messages={messages} limit={200} />
      </Card>
    </div>
  );
}
