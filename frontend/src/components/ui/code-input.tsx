"use client";

import { CircleAlert } from "lucide-react";
import { Fragment, useEffect, useId, useRef, useState, type ClipboardEvent, type KeyboardEvent } from "react";

import { interpolate } from "@/i18n/messages";
import { cn } from "@/lib/cn";

type Props = {
  name: string;
  label: string;
  /** Libellé de chaque case, avec {n} et {total}. */
  boxLabel: string;
  length?: number;
  kind?: "digits" | "letters";
  /** Tiret après cette case : le code de secours s'écrit ABCD-EFGH. */
  groupAt?: number;
  error?: string;
  defaultValue?: string;
  autoFocus?: boolean;
  /** Envoie le formulaire dès la dernière case remplie. */
  autoSubmit?: boolean;
  onValueChange?: (value: string) => void;
};

function clean(raw: string, kind: "digits" | "letters"): string[] {
  const found = raw.match(kind === "digits" ? /\d/g : /[a-z0-9]/gi) ?? [];
  return found.map((char) => char.toUpperCase());
}

/**
 * Code saisi case par case. Un code collé remplit toutes les cases depuis la première, où que
 * soit le curseur ; le remplissage automatique du téléphone passe par le même chemin. La
 * valeur part dans un champ caché : `FormData` et `useFormErrors` la lisent normalement.
 */
export function CodeInput({
  name,
  label,
  boxLabel,
  length = 6,
  kind = "digits",
  groupAt,
  error,
  defaultValue = "",
  autoFocus,
  autoSubmit,
  onValueChange,
}: Props) {
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const boxes = useRef<Array<HTMLInputElement | null>>([]);
  const [chars, setChars] = useState<string[]>(() => {
    const start = clean(defaultValue, kind).slice(0, length);
    return Array.from({ length }, (_, index) => start[index] ?? "");
  });
  const complete = chars.every(Boolean);
  const wasComplete = useRef(complete);
  const value = groupAt ? `${chars.slice(0, groupAt).join("")}-${chars.slice(groupAt).join("")}` : chars.join("");

  useEffect(() => {
    // Après le rendu : le champ caché porte déjà le code complet.
    if (autoSubmit && complete && !wasComplete.current) root.current?.closest("form")?.requestSubmit();
    wasComplete.current = complete;
  }, [autoSubmit, complete]);

  function focus(index: number) {
    const box = boxes.current[Math.max(0, Math.min(index, length - 1))];
    box?.focus();
    box?.select();
  }

  function update(next: string[]) {
    setChars(next);
    const joined = next.join("");
    onValueChange?.(joined && groupAt ? `${next.slice(0, groupAt).join("")}-${next.slice(groupAt).join("")}` : joined);
  }

  /** Remplit à partir d'une case et place le curseur sur la case suivante à compléter. */
  function fill(from: number, typed: string[]) {
    const next = [...chars];
    typed.slice(0, length - from).forEach((char, offset) => {
      next[from + offset] = char;
    });
    update(next);
    focus(from + typed.length);
  }

  function input(index: number, raw: string) {
    const typed = clean(raw, kind);
    if (typed.length === 0) {
      update(chars.map((char, position) => (position === index ? "" : char)));
      return;
    }
    if (typed.length === 1) return fill(index, typed);
    // Case déjà remplie : seul le dernier caractère est nouveau.
    if (typed.length === 2 && typed[0] === chars[index]) return fill(index, typed.slice(1));
    // Plusieurs caractères d'un coup : remplissage automatique du téléphone ou collage.
    fill(0, typed);
  }

  function paste(event: ClipboardEvent<HTMLInputElement>) {
    event.preventDefault();
    const typed = clean(event.clipboardData.getData("text"), kind);
    if (typed.length) fill(0, typed);
  }

  function keyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Backspace" && !chars[index] && index > 0) {
      event.preventDefault();
      update(chars.map((char, position) => (position === index - 1 ? "" : char)));
      focus(index - 1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      focus(index - 1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      focus(index + 1);
    }
  }

  return (
    <div data-field ref={root} className="flex flex-col gap-1.5">
      <span id={`${id}-label`} className="text-label font-medium">
        {label}
      </span>
      <input type="hidden" name={name} value={chars.some(Boolean) ? value : ""} />
      <div role="group" aria-labelledby={`${id}-label`} aria-describedby={error ? `${id}-error` : undefined} className="flex items-center gap-1.5 sm:gap-2" dir="ltr">
        {chars.map((char, index) => (
          <Fragment key={index}>
            {groupAt === index && (
              <span aria-hidden className="shrink-0 text-muted">
                -
              </span>
            )}
            <input
              ref={(element) => {
                boxes.current[index] = element;
              }}
              value={char}
              aria-label={interpolate(boxLabel, { n: index + 1, total: length })}
              aria-invalid={error ? true : undefined}
              // Le premier champ reçoit le code proposé par le clavier du téléphone.
              autoComplete={index === 0 && kind === "digits" ? "one-time-code" : "off"}
              inputMode={kind === "digits" ? "numeric" : "text"}
              autoCapitalize={kind === "digits" ? undefined : "characters"}
              spellCheck={false}
              enterKeyHint="go"
              autoFocus={autoFocus && index === 0}
              onChange={(event) => input(index, event.target.value)}
              onPaste={paste}
              onKeyDown={(event) => keyDown(index, event)}
              onFocus={(event) => event.target.select()}
              className={cn(
                "h-12 w-full max-w-14 min-w-0 rounded-lg border bg-card text-center text-input font-medium tabular-nums uppercase outline-none transition-[border-color,box-shadow] duration-200 focus:ring-[3px] sm:h-14 sm:text-h3",
                error ? "border-loss focus:ring-loss/15" : "focus:border-accent focus:ring-accent/15",
                !error && (char ? "border-muted/60" : "border-line hover:border-muted/60"),
              )}
            />
          </Fragment>
        ))}
      </div>
      {error && (
        <p id={`${id}-error`} aria-live="polite" className="flex animate-fade items-start gap-1.5 text-small text-loss">
          <CircleAlert size={14} strokeWidth={1.5} aria-hidden className="mt-0.5 shrink-0" />
          {error}
        </p>
      )}
    </div>
  );
}
