import Image from "next/image";

import type { Messages } from "@/i18n/messages";

/**
 * Connexion Google prévue pour plus tard : le bouton est présent mais désactivé et le
 * dit clairement. Aucune connexion n'est simulée tant que le service n'est pas branché.
 */
export function GoogleButton({ messages }: { messages: Messages }) {
  const t = messages.auth;
  return (
    <>
      <div className="flex items-center gap-3 text-small text-muted">
        <span aria-hidden className="h-px flex-1 bg-line" />
        {t.or}
        <span aria-hidden className="h-px flex-1 bg-line" />
      </div>
      <button
        type="button"
        disabled
        className="inline-flex h-12 w-full cursor-not-allowed items-center justify-center gap-2.5 rounded-lg border border-line bg-card px-4 text-label font-medium opacity-75"
      >
        <Image src="/icons/google.svg" alt="" width={18} height={18} unoptimized />
        {t.google}
        <span className="rounded-full bg-page px-2 py-0.5 text-small font-normal text-muted">{t.googleSoon}</span>
      </button>
    </>
  );
}
