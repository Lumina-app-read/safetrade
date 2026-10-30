import { describe, expect, it } from "vitest";

// Test de fumée : vérifie que l'outillage de test tourne en CI.
describe("test runner", () => {
  it("runs", () => {
    expect(1 + 1).toBe(2);
  });
});
