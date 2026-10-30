import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { AuthShell } from "@/components/auth/auth-shell";
import { ResetPasswordForm } from "@/components/auth/password-reset";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export async function generateMetadata({ params }: PageProps<"/[locale]/reset-password">): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale) ? { title: `${getMessages(locale).auth.reset.title} · SafeTrade` } : {};
}

export default async function Page({ params }: PageProps<"/[locale]/reset-password">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const messages = getMessages(locale);
  return (
    <AuthShell locale={locale} messages={messages}>
      <Suspense>
      <ResetPasswordForm locale={locale} messages={messages} />
      </Suspense>
    </AuthShell>
  );
}
