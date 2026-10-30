import { NextResponse, type NextRequest } from "next/server";

import { isLocale, LOCALE_COOKIE, negotiateLocale } from "@/i18n/config";

/**
 * Toute adresse sans préfixe de langue est redirigée vers /fr/... ou /en/... :
 * d'abord le choix enregistré (cookie), sinon la langue du navigateur.
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const first = pathname.split("/")[1];
  if (isLocale(first)) return;

  const saved = request.cookies.get(LOCALE_COOKIE)?.value;
  const locale = isLocale(saved) ? saved : negotiateLocale(request.headers.get("accept-language"));
  const url = request.nextUrl.clone();
  url.pathname = `/${locale}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(url);
}

export const config = {
  // Ni les fichiers internes de Next.js, ni l'API (/api/), ni les fichiers statiques.
  matcher: ["/((?!_next|api/|.*\\..*).*)"],
};
