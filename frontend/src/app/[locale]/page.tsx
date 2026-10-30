import { notFound } from "next/navigation";

import { PublicHeader } from "@/components/landing/public-header";
import { Faq, Features, FinalCta, Footer, Hero, HowItWorks, Markets, Pricing, Security } from "@/components/landing/sections";
import { isLocale } from "@/i18n/config";
import { getMessages } from "@/i18n/messages";

// Page publique de présentation (section 9 et directive front-end du 30 octobre 2026).
export default async function Home({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const messages = getMessages(locale);
  const props = { locale, messages };
  return (
    <div className="bg-card">
      <PublicHeader {...props} />
      <main>
        <Hero {...props} />
        <HowItWorks {...props} />
        <Markets {...props} />
        <Features {...props} />
        <Security {...props} />
        <Pricing {...props} />
        <Faq {...props} />
        <FinalCta {...props} />
      </main>
      <Footer {...props} />
    </div>
  );
}
