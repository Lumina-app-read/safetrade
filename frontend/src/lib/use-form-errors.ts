import { useRef, useState, type FocusEvent, type FormEvent } from "react";

import type { Rule } from "./validation";

type FieldElement = HTMLInputElement;
type Errors = Record<string, string | undefined>;

/**
 * Erreurs affichées sous les champs, à la place des bulles du navigateur (`noValidate`).
 *
 * - À l'envoi : tous les champs sont contrôlés, le premier en erreur reçoit le focus.
 * - En quittant un champ modifié : contrôle immédiat. Un champ vide jamais touché reste calme.
 * - Une erreur affichée se met à jour à chaque frappe et disparaît dès que c'est corrigé.
 */
export function useFormErrors(rules: Record<string, Rule>) {
  const [errors, setErrors] = useState<Errors>({});
  const edited = useRef(new Set<string>());

  function check(name: string, value: string) {
    setErrors((current) => ({ ...current, [name]: rules[name]?.(value) }));
  }

  function field(name: string) {
    return {
      name,
      error: errors[name],
      "aria-required": true,
      onBlur(event: FocusEvent<FieldElement>) {
        const target = event.relatedTarget as HTMLElement | null;
        // Vers le bouton d'envoi : ne pas déplacer ce bouton sous le pointeur.
        if (target instanceof HTMLButtonElement && target.type === "submit") return;
        // Vers le bouton « afficher » du même champ : la saisie n'est pas finie.
        if (target?.closest("[data-field]") === event.currentTarget.closest("[data-field]")) return;
        if (edited.current.has(name)) check(name, event.currentTarget.value);
      },
      onInput(event: FormEvent<FieldElement>) {
        edited.current.add(name);
        if (errors[name]) check(name, event.currentTarget.value);
      },
    };
  }

  /** Contrôle tout le formulaire ; renvoie vrai s'il peut partir. */
  function validate(form: HTMLFormElement): boolean {
    const next: Errors = {};
    let first: HTMLElement | null = null;
    for (const [name, rule] of Object.entries(rules)) {
      const element = form.elements.namedItem(name) as FieldElement | null;
      const message = rule(element?.value ?? "");
      next[name] = message;
      if (message && !first) first = element;
    }
    setErrors(next);
    first?.focus();
    return first === null;
  }

  /** Valeur d'un champ composé (cases d'un code) : même suivi qu'une frappe. */
  function change(name: string, value: string) {
    edited.current.add(name);
    if (errors[name]) check(name, value);
  }

  /** Erreur renvoyée par le serveur pour un champ précis. */
  function setError(name: string, message: string) {
    setErrors((current) => ({ ...current, [name]: message }));
  }

  return { errors, field, validate, setError, change };
}
