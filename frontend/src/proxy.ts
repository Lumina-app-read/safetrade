import { NextResponse, type NextRequest } from "next/server";

import { isLocale, LOCALE_COOKIE, negotiateLocale } from "@/i18n/config";

// En-têtes d'adresse client : jamais acceptés depuis le navigateur (usurpation possible).
const CLIENT_ADDRESS_HEADERS = ["x-forwarded-for", "x-real-ip", "forwarded"];

/**
 * 1. Requêtes /api (réécrites vers le backend) : retire les en-têtes d'adresse fournis par
 *    le client. En production, /api est servi directement par le reverse proxy, qui pose
 *    l'adresse réelle (docs/decisions/q16-adresse-ip-client.md).
 * 2. Pages sans préfixe de langue : redirection vers /fr/... ou /en/... (cookie, sinon
 *    langue du navigateur).
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/api/")) {
    const headers = new Headers(request.headers);
    CLIENT_ADDRESS_HEADERS.forEach((name) => headers.delete(name));
    return NextResponse.next({ request: { headers } });
  }

  const first = pathname.split("/")[1];
  if (isLocale(first)) return;

  const saved = request.cookies.get(LOCALE_COOKIE)?.value;
  const locale = isLocale(saved) ? saved : negotiateLocale(request.headers.get("accept-language"));
  const url = request.nextUrl.clone();
  url.pathname = `/${locale}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(url);
}

export const config = {
  // Ni les fichiers internes de Next.js, ni les fichiers statiques.
  matcher: ["/((?!_next|.*\\..*).*)"],
};
