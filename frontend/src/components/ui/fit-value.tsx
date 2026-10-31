import type { CSSProperties, ReactNode } from "react";

import { SignedAmount } from "./amount";

/**
 * Valeur d'une carte : la taille s'adapte à la longueur du texte et à la largeur disponible,
 * en CSS seul (`text-fit`). Un montant ne peut donc pas sortir de sa carte, quel qu'il soit.
 */
export function FitValue({
  text,
  size = "kpi",
  extra = 0,
  title,
  children,
}: {
  /** Texte affiché, pour calculer la taille. */
  text: string;
  size?: "kpi" | "h3";
  /** Largeur en plus du texte, en caractères (icône, signe). */
  extra?: number;
  title?: string;
  children?: ReactNode;
}) {
  const style = { "--chars": text.length + extra } as CSSProperties;
  return (
    <div className="@container w-full min-w-0">
      <div className={size === "kpi" ? "text-fit" : "text-fit-h3"} style={style} title={title}>
        {children ?? text}
      </div>
    </div>
  );
}

/** Gain ou perte dans une carte : signe, icône et couleur, sans jamais déborder. */
export function FitAmount({
  value,
  formatted,
  title,
  size,
}: {
  value: number;
  formatted: string;
  title?: string;
  size?: "kpi" | "h3";
}) {
  return (
    <FitValue text={formatted} extra={value === 0 ? 0 : 3} size={size} title={title}>
      <SignedAmount value={value} formatted={formatted} />
    </FitValue>
  );
}
