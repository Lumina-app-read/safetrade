import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { AuthShell } from "@/components/auth/auth-shell";
import { ReferredRegisterForm, RegisterForm } from "@/components/auth/register-form";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

export async function generateMetadata({ params }: PageProps<"/[locale]/register">): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale) ? { title: `${getMessages(locale).auth.register.title} · SafeTrade` } : {};
}

export default async function RegisterPage({ params }: PageProps<"/[locale]/register">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const messages = getMessages(locale);
  return (
    <AuthShell locale={locale} messages={messages}>
      {/* Page statique : le code du lien de parrainage est lu dans le navigateur. */}
      <Suspense fallback={<RegisterForm locale={locale} messages={messages} />}>
        <ReferredRegisterForm locale={locale} messages={messages} />
      </Suspense>
    </AuthShell>
  );
}
