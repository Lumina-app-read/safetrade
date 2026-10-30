import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div {...rest} className={cn("rounded-xl border border-line bg-card p-6 shadow-card", className)} />;
}

/** Titre de section : petit, en majuscules, espacé (référence visuelle, section 15). */
export function SectionTitle({ className, ...rest }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2 {...rest} className={cn("mt-8 mb-3 text-small font-medium tracking-[0.08em] text-muted uppercase", className)} />
  );
}
