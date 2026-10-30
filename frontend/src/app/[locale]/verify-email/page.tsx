import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { AuthShell } from "@/components/auth/auth-shell";
import { VerifyEmail } from "@/components/auth/verify-email";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export async function generateMetadata({ params }: PageProps<"/[locale]/verify-email">): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale) ? { title: `${getMessages(locale).auth.verify.title} · SafeTrade` } : {};
}

export default async function VerifyEmailPage({ params }: PageProps<"/[locale]/verify-email">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const messages = getMessages(locale);
  return (
    <AuthShell locale={locale} messages={messages}>
      {/* Le jeton est lu dans l'adresse côté navigateur. */}
      <Suspense>
        <VerifyEmail locale={locale} messages={messages} />
      </Suspense>
    </AuthShell>
  );
}
