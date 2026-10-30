import { CirclePause, OctagonAlert, Play, Wallet } from "lucide-react";

import { TopBar } from "@/components/top-bar";
import { SignedAmount } from "@/components/ui/amount";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, SectionTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Table, Td, Th } from "@/components/ui/table";
import { getMessages } from "@/lib/messages";

// Page de démonstration des composants (étape 1.2). Les montants sont fictifs.
export default function ComponentsDemo() {
  const m = getMessages("fr");
  const t = m.demo;
  const usd = (n: number) =>
    new Intl.NumberFormat("fr-FR", { style: "currency", currency: "USD", currencyDisplay: "code" }).format(n);
  const rows = [
    { asset: "Volatility 75 Index", stake: 1, result: 0.18, tone: "gain" as const, status: t.badgeGain },
    { asset: "Volatility 100 Index", stake: 1, result: -0.5, tone: "loss" as const, status: t.badgeLoss },
    { asset: "Boom 500 Index", stake: 1, result: 0.07, tone: "neutral" as const, status: t.badgeNeutral },
  ];

  return (
    <>
      <TopBar messages={m} current="dashboard" />
      <main className="mx-auto max-w-[1200px] px-4 pt-8 pb-24 sm:px-6">
        <h1 className="text-h1">{t.title}</h1>
        <p className="text-small text-muted">{t.subtitle}</p>

        <SectionTitle>{t.buttons}</SectionTitle>
        <Card className="flex flex-wrap gap-3">
          <Button variant="primary">{t.primary}</Button>
          <Button variant="accent" icon={<Play size={20} strokeWidth={1.5} aria-hidden />}>
            {t.accent}
          </Button>
          <Button icon={<CirclePause size={20} strokeWidth={1.5} aria-hidden />}>{t.ghost}</Button>
          <Button variant="danger" icon={<OctagonAlert size={20} strokeWidth={1.5} aria-hidden />}>
            {t.danger}
          </Button>
          <Button variant="accent" pending>
            {t.pending}
          </Button>
        </Card>

        <SectionTitle>{t.badges}</SectionTitle>
        <Card className="flex flex-wrap gap-3">
          <Badge tone="gain">{t.badgeGain}</Badge>
          <Badge tone="loss">{t.badgeLoss}</Badge>
          <Badge tone="warn">{t.badgeWarn}</Badge>
          <Badge tone="neutral">{t.badgeNeutral}</Badge>
          <Badge tone="brand">{t.badgeBrand}</Badge>
        </Card>

        <SectionTitle>{t.fields}</SectionTitle>
        <Card className="grid gap-4 sm:grid-cols-2">
          <Field label={t.stake} unit="USD" defaultValue="1" inputMode="decimal" hint={t.stakeHint} />
          <Field label={t.stopLoss} unit={t.ofStake} defaultValue="5" inputMode="decimal" error={t.stopLossError} />
        </Card>

        <SectionTitle>{t.cards}</SectionTitle>
        <div className="grid gap-4 sm:grid-cols-2">
          <Card className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-muted">
              <span className="text-label font-medium">{t.balance}</span>
              <Wallet size={20} strokeWidth={1.5} aria-hidden />
            </div>
            <div className="text-kpi font-medium tabular-nums">{usd(10012.4)}</div>
          </Card>
          <Card className="flex flex-col gap-2">
            <span className="text-label font-medium text-muted">{t.today}</span>
            <div className="text-kpi font-medium">
              <SignedAmount value={12.4} formatted={usd(12.4)} />
            </div>
          </Card>
        </div>
        <div className="relative mt-4 overflow-hidden rounded-xl bg-anthracite p-8 text-on-anthracite">
          <span aria-hidden className="absolute -top-28 -right-24 size-80 rounded-full border-[40px] border-brand-ring" />
          <p className="relative text-h2">SafeTrade</p>
        </div>

        <SectionTitle>{t.table}</SectionTitle>
        <Card>
          <Table>
            <thead>
              <tr>
                <Th>{t.asset}</Th>
                <Th numeric>{t.stakeCol}</Th>
                <Th numeric>{t.result}</Th>
                <Th>{t.status}</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.asset}>
                  <Td>{r.asset}</Td>
                  <Td numeric>{usd(r.stake)}</Td>
                  <Td numeric>
                    <SignedAmount value={r.result} formatted={usd(Math.abs(r.result) * Math.sign(r.result))} />
                  </Td>
                  <Td>
                    <Badge tone={r.tone}>{r.status}</Badge>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>

        <SectionTitle>{t.typography}</SectionTitle>
        <Card className="flex flex-col gap-3">
          <p className="text-h1">{t.h1}</p>
          <p className="text-h2">{t.h2}</p>
          <p className="text-h3 font-medium">{t.h3}</p>
          <p className="text-body">{t.body}</p>
          <p className="text-small text-muted">{t.small}</p>
        </Card>
      </main>
    </>
  );
}
