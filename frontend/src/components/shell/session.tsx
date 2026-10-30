"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { Locale } from "@/i18n/config";
import type { Messages } from "@/i18n/messages";
import { api } from "@/lib/api";

export type SessionUser = {
  id: string;
  email: string;
  first_name: string;
  role: string;
  mfa_enabled: boolean;
};

type Session = { user: SessionUser; refresh: () => void };

const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession doit être utilisé sous SessionGate");
  return session;
}

/**
 * N'affiche son contenu qu'une fois la session confirmée par le serveur. Sans session
 * valide, redirection vers la connexion : le front-end ne décide jamais seul de l'accès.
 */
export function SessionGate({ locale, messages, children }: { locale: Locale; messages: Messages; children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<SessionUser | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    api<{ user: SessionUser }>("/auth/me").then((result) => {
      if (!active) return;
      if (result.ok) {
        setUser(result.data.user);
        setFailed(false);
      } else if (result.status === 401 || result.status === 403) {
        router.replace(`/${locale}/login`);
      } else {
        setFailed(true);
      }
    });
    return () => {
      active = false;
    };
  }, [locale, router, attempt]);

  const refresh = useCallback(() => setAttempt((n) => n + 1), []);
  const value = useMemo(() => (user ? { user, refresh } : null), [user, refresh]);

  if (failed && !user) {
    return (
      <div className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-4 px-5">
        <Alert tone="error">{messages.shell.loadError}</Alert>
        <Button size="lg" onClick={refresh}>
          {messages.shell.retry}
        </Button>
      </div>
    );
  }
  if (!value) {
    return (
      <p role="status" className="grid min-h-dvh animate-fade place-items-center px-5 text-muted">
        {messages.shell.loading}
      </p>
    );
  }
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
