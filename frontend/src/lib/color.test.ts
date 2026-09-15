import { describe, expect, it } from "vitest";
import { contrastRatio, deriveAccent, ensureContrast, relativeLuminance } from "@/lib/color";

const WHITE = "#FFFFFF";
const BRAND_DARK_BG = "#0B1210";
const ACCENT = "#3B82F6";
const INKS = { dark: "#04122B", light: "#EDEFED" };

describe("relativeLuminance", () => {
  it("spans black to white", () => {
    expect(relativeLuminance("#000000")).toBe(0);
    expect(relativeLuminance(WHITE)).toBeCloseTo(1, 5);
  });

  it("linearises sRGB rather than averaging raw channels", () => {
    expect(relativeLuminance("#808080")).toBeCloseTo(0.2159, 3);
  });
});

describe("contrastRatio", () => {
  it("is 21 for black on white and symmetric", () => {
    expect(contrastRatio("#000000", WHITE)).toBeCloseTo(21, 2);
    expect(contrastRatio(WHITE, "#000000")).toBeCloseTo(21, 2);
  });

  it("scores the brand accent as failing on white but passing on the brand dark", () => {
    expect(contrastRatio(ACCENT, WHITE)).toBeCloseTo(3.68, 1);
    expect(contrastRatio(ACCENT, BRAND_DARK_BG)).toBeGreaterThan(4.5);
  });
});

describe("ensureContrast", () => {
  it("darkens an accent that is too light for a light background", () => {
    const fixed = ensureContrast(ACCENT, WHITE, 4.5);
    expect(contrastRatio(fixed, WHITE)).toBeGreaterThanOrEqual(4.5);
    expect(relativeLuminance(fixed)).toBeLessThan(relativeLuminance(ACCENT));
  });

  it("lightens an accent that is too dark for a dark background", () => {
    const fixed = ensureContrast("#0D1B3A", BRAND_DARK_BG, 4.5);
    expect(contrastRatio(fixed, BRAND_DARK_BG)).toBeGreaterThanOrEqual(4.5);
    expect(relativeLuminance(fixed)).toBeGreaterThan(relativeLuminance("#0D1B3A"));
  });

  it("leaves a color that already passes untouched", () => {
    expect(ensureContrast(ACCENT, BRAND_DARK_BG, 4.5)).toBe(ACCENT);
  });

  it("uses the lower UI threshold when asked for 3:1", () => {
    const ring = ensureContrast(ACCENT, WHITE, 3);
    expect(ring).toBe(ACCENT);
  });
});

describe("deriveAccent", () => {
  it("satisfies the page background and the on-accent text at once", () => {
    for (const background of [WHITE, BRAND_DARK_BG]) {
      const { color, on } = deriveAccent(ACCENT, background, INKS, 4.5);
      expect(contrastRatio(color, background)).toBeGreaterThanOrEqual(4.5);
      expect(contrastRatio(on, color)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("keeps the brand accent and ink untouched on the brand dark surface", () => {
    expect(deriveAccent(ACCENT, BRAND_DARK_BG, INKS, 4.5)).toEqual({
      color: ACCENT,
      on: "#04122B",
    });
  });

  it("picks the ink on the same side as the shift", () => {
    expect(deriveAccent(ACCENT, WHITE, INKS, 4.5).on).toBe("#EDEFED");
    expect(deriveAccent("#1E3A8A", BRAND_DARK_BG, INKS, 4.5).on).toBe("#04122B");
  });

  it("stays readable for accents the brand palette never anticipated", () => {
    for (const hex of ["#FFFF00", "#000000", "#FFFFFF", "#7F7F7F"]) {
      for (const background of [WHITE, BRAND_DARK_BG]) {
        const { color, on } = deriveAccent(hex, background, INKS, 4.5);
        expect(contrastRatio(color, background)).toBeGreaterThanOrEqual(4.49);
        expect(contrastRatio(on, color)).toBeGreaterThanOrEqual(4.49);
      }
    }
  });
});
