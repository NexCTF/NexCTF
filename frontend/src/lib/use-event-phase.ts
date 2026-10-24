import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { getPublicInfo } from "@/lib/api";

export interface EventPhase {
  start: Date | null;
  freeze: Date | null;
  end: Date | null;
  upcoming: boolean;
  running: boolean;
  frozen: boolean;
  ended: boolean;
  /** Whether answers and hint unlocks are accepted right now. */
  open: boolean;
}

/** Longest delay `setTimeout` accepts before it fires immediately. */
const MAX_TIMEOUT_MS = 2_147_483_647;

function toDate(iso: string | undefined): Date | null {
  return iso ? new Date(iso) : null;
}

/** Current time, re-read when *now* crosses the next of *boundaries*. */
function useNowAcross(boundaries: (Date | null)[]): Date {
  const [now, setNow] = useState(() => new Date());
  const next = Math.min(
    ...boundaries.map((b) => b?.getTime() ?? Infinity).filter((ms) => ms > now.getTime()),
  );

  useEffect(() => {
    if (next === Infinity) return;
    let timer: ReturnType<typeof setTimeout>;
    const arm = () => {
      const remaining = next - Date.now() + 1;
      timer =
        remaining > MAX_TIMEOUT_MS
          ? setTimeout(arm, MAX_TIMEOUT_MS)
          : setTimeout(() => setNow(new Date()), remaining);
    };
    arm();
    return () => clearTimeout(timer);
  }, [next]);

  return now;
}

/** Event times from the public info and where *now* falls among them. */
export function useEventPhase(): EventPhase {
  const { data: info } = useQuery({
    queryKey: ["info", "public"],
    queryFn: getPublicInfo,
    staleTime: 5 * 60 * 1000,
  });
  const start = toDate(info?.competition.start_time);
  const freeze = toDate(info?.competition.freeze_time);
  const end = toDate(info?.competition.end_time);
  const now = useNowAcross([start, freeze, end]);
  const upcoming = start !== null && now < start;
  const ended = end !== null && now > end;
  return {
    start,
    freeze,
    end,
    upcoming,
    running: !upcoming && !ended && (start !== null || end !== null),
    frozen: freeze !== null && now >= freeze,
    ended,
    open: !upcoming && !ended,
  };
}
