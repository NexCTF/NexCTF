/** WCAG color math, used to derive readable shades from a single brand accent. */

type Rgb = [number, number, number];

function parseHex(hex: string): Rgb {
  const h = hex.replace("#", "");
  return [0, 2, 4].map((i) => Number.parseInt(h.slice(i, i + 2), 16)) as Rgb;
}

function toHex(rgb: Rgb): string {
  const part = (c: number) => Math.round(c).toString(16).padStart(2, "0");
  return `#${rgb.map(part).join("")}`;
}

function channelLuminance(channel: number): number {
  const c = channel / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

/** WCAG 2.1 relative luminance, 0 (black) to 1 (white). */
export function relativeLuminance(hex: string): number {
  const [r, g, b] = parseHex(hex).map(channelLuminance);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG 2.1 contrast ratio, 1 to 21. */
export function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function mix(hex: string, toward: Rgb, amount: number): string {
  const rgb = parseHex(hex);
  return toHex(rgb.map((c, i) => c + (toward[i] - c) * amount) as Rgb);
}

const BLACK: Rgb = [0, 0, 0];
const WHITE: Rgb = [255, 255, 255];

function isLightSurface(background: string): boolean {
  return relativeLuminance(background) > 0.18;
}

/** Away from `background` means darker on a light surface, lighter on a dark one. */
function awayFrom(background: string): Rgb {
  return isLightSurface(background) ? BLACK : WHITE;
}

/** Smallest shift of `color` away from `background` for which `passes` holds. */
function shiftUntil(color: string, background: string, passes: (shade: string) => boolean): string {
  if (passes(color)) return color;
  const toward = awayFrom(background);
  let low = 0;
  let high = 1;
  for (let i = 0; i < 16; i++) {
    const mid = (low + high) / 2;
    if (passes(mix(color, toward, mid))) high = mid;
    else low = mid;
  }
  return mix(color, toward, high);
}

/**
 * Shift `color` away from `background` until it reaches `target` contrast.
 * Returns `color` unchanged when it already passes.
 */
export function ensureContrast(color: string, background: string, target: number): string {
  return shiftUntil(color, background, (shade) => contrastRatio(shade, background) >= target);
}

export interface Accent {
  /** The accent itself, readable as text on `background`. */
  color: string;
  /** Text placed on top of an accent fill. */
  on: string;
}

/**
 * Derive an accent and its on-accent text, both at `target` contrast.
 *
 * Shifting the accent away from `background` raises both ratios at once, so the
 * ink is whichever of `inks` sits on the same side as that shift.
 */
export function deriveAccent(
  accent: string,
  background: string,
  inks: { light: string; dark: string },
  target: number,
): Accent {
  const on = isLightSurface(background) ? inks.light : inks.dark;
  const color = shiftUntil(
    accent,
    background,
    (shade) => contrastRatio(shade, background) >= target && contrastRatio(on, shade) >= target,
  );
  return { color, on };
}
