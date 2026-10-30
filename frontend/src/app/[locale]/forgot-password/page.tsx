import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AuthShell } from "@/components/auth/auth-shell";
import { ForgotPasswordForm } from "@/components/auth/password-reset";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export async function generateMetadata({ params }: PageProps<"/[locale]/forgot-password">): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale) ? { title: `${getMessages(locale).auth.forgot.title} · SafeTrade` } : {};
}

export default async function Page({ params }: PageProps<"/[locale]/forgot-password">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const messages = getMessages(locale);
  return (
    <AuthShell locale={locale} messages={messages}>
      <ForgotPasswordForm locale={locale} messages={messages} />
    </AuthShell>
  );
}
