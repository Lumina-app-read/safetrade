import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SafeTrade",
};

// Langue, police et thèmes sont mis en place aux étapes 1.2 et 1.3.
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
