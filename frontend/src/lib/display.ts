import type { Notification } from "@/lib/api";

/** Search params of the `/display` page, as typed in the URL. */
export interface DisplaySearch {
  bracket?: string;
  rotate?: number;
  scale?: number;
}

/** Resolved settings of one display screen. */
export interface DisplayOptions {
  /** Bracket shown permanently; rotation is off when set. */
  bracket: string | undefined;
  /** Seconds between two brackets, 0 when rotation is off. */
  rotate: number;
  /** Zoom factor of the whole screen. */
  scale: number;
}

export const ROTATE_RANGE = [10, 600] as const;
const SCALE_RANGE = [0.5, 3] as const;
const DEFAULT_SCALE = 1;
/** How far back a broadcast stays in the ticker. */
const RECENT_BROADCAST_MS = 30 * 60_000;

function toNumber(value: unknown): number | undefined {
  const n = typeof value === "number" ? value : Number(value);
  return typeof value !== "boolean" && value !== "" && Number.isFinite(n) ? n : undefined;
}

function clamp(value: number, [min, max]: readonly [number, number]): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * Keep the known `/display` params. The router JSON-parses search values, so a bracket
 * named "2025" or "true" arrives as a number or boolean and is turned back into text.
 */
export function parseDisplaySearch(search: Record<string, unknown>): DisplaySearch {
  const raw = search.bracket;
  const bracket = ["string", "number", "boolean"].includes(typeof raw) ? String(raw) : "";
  return {
    bracket: bracket || undefined,
    rotate: toNumber(search.rotate),
    scale: toNumber(search.scale),
  };
}

/** Apply defaults and bounds to the `/display` params. */
export function resolveDisplayOptions(search: DisplaySearch): DisplayOptions {
  const rotate = Math.round(search.rotate ?? 0);
  return {
    bracket: search.bracket,
    rotate: search.bracket || rotate <= 0 ? 0 : clamp(rotate, ROTATE_RANGE),
    scale: clamp(search.scale ?? DEFAULT_SCALE, SCALE_RANGE),
  };
}

/** Path and query of the `/display` page for *options*, leaving defaults out. */
export function displayPath(options: DisplayOptions): string {
  const params = new URLSearchParams();
  if (options.bracket) params.set("bracket", options.bracket);
  if (options.rotate) params.set("rotate", String(options.rotate));
  if (options.scale !== DEFAULT_SCALE) params.set("scale", String(options.scale));
  const query = params.toString();
  return query ? `/display?${query}` : "/display";
}

/** The API token carried in a `/display` link's fragment (`#token=…`), if any. */
export function displayTokenFromHash(hash: string): string | null {
  return new URLSearchParams(hash.replace(/^#/, "")).get("token") || null;
}

/** Format a remaining duration as `H:MM:SS`, prefixed with days (`2d`) past 24 hours. */
export function formatCountdown(ms: number, dayUnit = "d"): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const days = Math.floor(total / 86_400);
  const hours = Math.floor((total % 86_400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  const clock = `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  return days > 0 ? `${days}${dayUnit} ${clock}` : clock;
}

/** One team's place in a refresh of the ranking. */
interface Standing {
  team_id: string;
  rank: number;
  total: number;
}

/** How a team moved since the previous refresh. */
export interface StandingChange {
  /** Places gained (positive) or lost (negative). */
  rankDelta: number;
  scored: boolean;
}

/** Teams that moved or scored between two refreshes, keyed by team id; new teams are skipped. */
export function diffStandings(
  previous: Standing[],
  current: Standing[],
): Map<string, StandingChange> {
  const before = new Map(previous.map((s) => [s.team_id, s]));
  const changes = new Map<string, StandingChange>();
  for (const entry of current) {
    const old = before.get(entry.team_id);
    if (!old) continue;
    const rankDelta = old.rank - entry.rank;
    const scored = entry.total > old.total;
    if (rankDelta !== 0 || scored) changes.set(entry.team_id, { rankDelta, scored });
  }
  return changes;
}

/** Broadcasts sent in the last 30 minutes before *now*, newest first. */
export function recentBroadcasts(notifications: Notification[], now: number): Notification[] {
  return notifications
    .map((n) => ({ n, at: Date.parse(n.created_at) }))
    .filter(({ n, at }) => n.is_broadcast && now - at <= RECENT_BROADCAST_MS)
    .sort((a, b) => b.at - a.at)
    .map(({ n }) => n);
}
