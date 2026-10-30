"use client";

import { useEffect, useRef, type CSSProperties, type ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * Fait apparaître son contenu quand il entre à l'écran (IntersectionObserver, sans
 * bibliothèque). Styles dans globals.css ; neutralisé par prefers-reduced-motion.
 */
export function Reveal({
  children,
  delay = 0,
  className,
  as: Tag = "div",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "li" | "section";
}) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          el.dataset.shown = "";
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -10% 0px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <Tag
      ref={ref as never}
      data-reveal=""
      style={{ "--reveal-delay": `${delay}ms` } as CSSProperties}
      className={cn(className)}
    >
      {children}
    </Tag>
  );
}
