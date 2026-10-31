/**
 * Contrôles de saisie côté navigateur : un confort, jamais une garantie. Le serveur revalide
 * tout (règle d'or) ; les seuils du mot de passe reprennent ceux du backend.
 */

import type { Messages } from "@/i18n/messages";

export type Rule = (value: string) => string | undefined;
export type Texts = Messages["auth"]["validation"];

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export const PASSWORD_RULES = [
  { key: "ruleLength", test: (p: string) => p.length >= 10 },
  { key: "ruleVariety", test: (p: string) => new Set(p).size >= 4 },
] as const;

export function emailRule(t: Texts): Rule {
  return (value) => {
    const email = value.trim();
    if (!email) return t.emailRequired;
    return EMAIL.test(email) ? undefined : t.emailInvalid;
  };
}

export function requiredRule(message: string): Rule {
  return (value) => (value.trim() ? undefined : message);
}

/** Connexion : seule la présence compte, l'ancienne politique ne doit bloquer personne. */
export function currentPasswordRule(t: Texts): Rule {
  return (value) => (value ? undefined : t.passwordRequired);
}

export function newPasswordRule(t: Texts): Rule {
  return (value) => {
    if (!value) return t.passwordRequired;
    if (value.length > 128) return t.passwordTooLong;
    return PASSWORD_RULES.every(({ test }) => test(value)) ? undefined : t.passwordWeak;
  };
}

export function totpRule(t: Texts): Rule {
  return (value) => {
    const code = value.replace(/\s/g, "");
    if (!code) return t.codeRequired;
    return /^\d{6}$/.test(code) ? undefined : t.codeInvalid;
  };
}

export function recoveryRule(t: Texts): Rule {
  return (value) => {
    const code = value.trim();
    if (!code) return t.codeRequired;
    return /^[A-Za-z0-9]{4}-?[A-Za-z0-9]{4}$/.test(code) ? undefined : t.recoveryInvalid;
  };
}
