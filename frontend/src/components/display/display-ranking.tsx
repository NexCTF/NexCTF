import { ArrowDown, ArrowUp } from "lucide-react";
import { memo, type RefObject, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { MEDALS } from "@/components/scoreboard";
import { useAutoScroll } from "@/hooks/use-auto-scroll";
import type { ScoreboardEntry } from "@/lib/api";
import { diffStandings, type StandingChange } from "@/lib/display";
import { cn } from "@/lib/utils";

/** Height a ranking row aims for, in CSS pixels; rows then stretch to fill the screen exactly. */
const ROW_TARGET_PX = 56;
const MIN_ROWS = 3;
const FALLBACK_ROWS = 15;
/** How long a rank change or new score stays highlighted. */
const HIGHLIGHT_MS = 10_000;
const NO_CHANGES = new Map<string, StandingChange>();

/** How many rows of about ROW_TARGET_PX fit in *viewport*, kept up to date on resize. */
function useRowsThatFit(viewport: RefObject<HTMLElement | null>): number {
  const [rows, setRows] = useState(FALLBACK_ROWS);

  useEffect(() => {
    const el = viewport.current;
    if (!el) return;
    const measure = () => {
      if (el.clientHeight > 0) {
        setRows(Math.max(MIN_ROWS, Math.round(el.clientHeight / ROW_TARGET_PX)));
      }
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [viewport]);

  return rows;
}

/** Teams that moved or scored on the last refresh, cleared after HIGHLIGHT_MS. */
function useStandingChanges(entries: ScoreboardEntry[]): Map<string, StandingChange> {
  const previous = useRef(entries);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [changes, setChanges] = useState(NO_CHANGES);

  useEffect(() => {
    const diff = diffStandings(previous.current, entries);
    previous.current = entries;
    if (diff.size === 0) return;
    setChanges(diff);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setChanges(NO_CHANGES), HIGHLIGHT_MS);
  }, [entries]);

  useEffect(() => () => clearTimeout(timer.current), []);

  return changes;
}

function RankDelta({ delta }: { delta: number }) {
  if (delta === 0) return <span />;
  const Icon = delta > 0 ? ArrowUp : ArrowDown;
  return (
    <span
      className={cn(
        "flex items-center text-[45cqh] font-semibold tabular-nums",
        delta > 0 ? "text-green-400" : "text-red-400",
      )}
    >
      <Icon className="size-[1em]" />
      {Math.abs(delta)}
    </span>
  );
}

const RankingRow = memo(function RankingRow({
  entry,
  change,
  rows,
  showBracket,
}: {
  entry: ScoreboardEntry;
  change: StandingChange | undefined;
  rows: number;
  showBracket: boolean;
}) {
  return (
    <li className="group py-[3px]" style={{ height: `calc(100cqh / ${rows})` }}>
      <div
        style={{ containerType: "size" }}
        className={cn(
          "grid h-full grid-cols-[1.5fr_1fr_10fr_4fr] items-center gap-6 rounded-lg px-6 transition-colors duration-1000",
          change?.scored ? "bg-primary/20" : "group-odd:bg-muted/40",
        )}
      >
        <span
          className={cn(
            "flex aspect-square h-[80cqh] items-center justify-center justify-self-start rounded-full text-[50cqh] font-bold tabular-nums",
            MEDALS[entry.rank] ?? "text-muted-foreground",
          )}
        >
          {entry.rank}
        </span>
        <RankDelta delta={change?.rankDelta ?? 0} />
        <span className="flex min-w-0 items-baseline gap-4">
          <span className="truncate text-[55cqh] font-semibold">{entry.team_name}</span>
          {showBracket && entry.team_bracket && (
            <span className="shrink-0 text-[35cqh] capitalize text-muted-foreground">
              {entry.team_bracket}
            </span>
          )}
        </span>
        <span className="text-right text-[60cqh] font-bold tabular-nums">
          {entry.total.toLocaleString()}
        </span>
      </div>
    </li>
  );
});

/**
 * Every team, as many rows as fit the screen, scrolling through the rest. Mount one per
 * view (keyed by bracket) so highlights and scrolling start over on a switch.
 */
export const DisplayRanking = memo(function DisplayRanking({
  entries,
  showBracket,
}: {
  entries: ScoreboardEntry[];
  showBracket: boolean;
}) {
  const { t } = useTranslation();
  const viewport = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLOListElement>(null);
  const rows = useRowsThatFit(viewport);
  const changes = useStandingChanges(entries);
  useAutoScroll(viewport, list, rows);

  return (
    <div
      ref={viewport}
      className="relative h-full overflow-hidden"
      style={{ containerType: "size" }}
    >
      {entries.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-3xl text-muted-foreground">
          {t("scoreboard.empty")}
        </div>
      )}
      <ol ref={list} className="will-change-transform">
        {entries.map((entry) => (
          <RankingRow
            key={entry.team_id}
            entry={entry}
            change={changes.get(entry.team_id)}
            rows={rows}
            showBracket={showBracket}
          />
        ))}
      </ol>
    </div>
  );
});
