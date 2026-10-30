import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";

import { DEFAULT_THEME, themeInitScript } from "@/lib/theme";

import "./globals.css";

// Auto-hébergée par next/font : aucune requête vers Google côté navigateur.
const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-jakarta",
  display: "swap",
});

export const metadata: Metadata = {
  title: "SafeTrade",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // data-theme est modifié avant l'hydratation par le script ci-dessous.
    <html lang="fr" data-theme={DEFAULT_THEME} className={jakarta.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
