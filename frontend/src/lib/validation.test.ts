import { describe, expect, it } from "vitest";

import { getMessages } from "@/i18n/messages";

import {
  currentPasswordRule,
  emailRule,
  newPasswordRule,
  recoveryRule,
  requiredRule,
  totpRule,
} from "./validation";

describe.each(["fr", "en"] as const)("contrôles de saisie (%s)", (locale) => {
  const t = getMessages(locale).auth.validation;

  it("exige une adresse e-mail valide", () => {
    const rule = emailRule(t);
    expect(rule("")).toBe(t.emailRequired);
    expect(rule("   ")).toBe(t.emailRequired);
    for (const bad of ["ada", "ada@", "@site.com", "ada@site", "a b@site.com", "ada@site.c"]) {
      expect(rule(bad)).toBe(t.emailInvalid);
    }
    expect(rule(" ada@site.com ")).toBeUndefined();
  });

  it("n'applique pas la politique au mot de passe de connexion", () => {
    const rule = currentPasswordRule(t);
    expect(rule("")).toBe(t.passwordRequired);
    expect(rule("court")).toBeUndefined();
  });

  it("applique la politique au nouveau mot de passe", () => {
    const rule = newPasswordRule(t);
    expect(rule("")).toBe(t.passwordRequired);
    expect(rule("court")).toBe(t.passwordWeak);
    expect(rule("aaaaaaaaaaaa")).toBe(t.passwordWeak);
    expect(rule("x".repeat(129))).toBe(t.passwordTooLong);
    expect(rule("Correct-Horse-42")).toBeUndefined();
  });

  it("contrôle les codes de double authentification", () => {
    expect(totpRule(t)("")).toBe(t.codeRequired);
    expect(totpRule(t)("12345")).toBe(t.codeInvalid);
    expect(totpRule(t)("123 456")).toBeUndefined();
    expect(recoveryRule(t)("ABCD")).toBe(t.recoveryInvalid);
    expect(recoveryRule(t)("ABCD-EF12")).toBeUndefined();
  });

  it("refuse un champ fait d'espaces", () => {
    expect(requiredRule(t.firstNameRequired)("  ")).toBe(t.firstNameRequired);
    expect(requiredRule(t.firstNameRequired)("Ada")).toBeUndefined();
  });
});
