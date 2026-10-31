import { ArrowLeft, Hourglass } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import type { Locale } from "@/i18n/config";
import type { Messages } from "@/i18n/messages";

/** Section prévue mais pas encore construite : un état honnête, sans donnée inventée. */
export function ComingSoon({
  locale,
  messages,
  title,
  body,
  children,
}: {
  locale: Locale;
  messages: Messages;
  title: string;
  body: string;
  children?: ReactNode;
}) {
  return (
    <>
      <h1 className="text-h1">{title}</h1>
      {children}
      <div className="mt-6 flex flex-col items-start gap-4 rounded-xl border border-dashed border-line bg-card p-6">
        <span className="grid size-11 place-items-center rounded-xl bg-accent-soft text-accent-text">
          <Hourglass size={20} strokeWidth={1.5} aria-hidden />
        </span>
        <div>
          <h2 className="text-h3 font-medium">{messages.soon.title}</h2>
          <p className="mt-1 max-w-xl text-muted">{body}</p>
        </div>
        <Link
          href={`/${locale}/dashboard`}
          className="inline-flex h-11 items-center gap-1.5 text-label font-medium text-accent-text underline-offset-4 hover:underline"
        >
          <ArrowLeft size={16} strokeWidth={1.5} aria-hidden />
          {messages.soon.back}
        </Link>
      </div>
    </>
  );
}
