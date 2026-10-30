import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { getPublicInfo } from "@/lib/api";
import { serverNow } from "@/lib/server-clock";

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

/** Server time, re-read when it crosses the next of *boundaries* or *syncedAt* changes. */
function useNowAcross(boundaries: (Date | null)[], syncedAt: string | undefined): Date {
  const [now, setNow] = useState(() => new Date(serverNow()));

  useEffect(() => {
    if (syncedAt) setNow(new Date(serverNow()));
  }, [syncedAt]);

  const next = Math.min(
    ...boundaries.map((b) => b?.getTime() ?? Infinity).filter((ms) => ms > now.getTime()),
  );

  useEffect(() => {
    if (next === Infinity) return;
    let timer: ReturnType<typeof setTimeout>;
    const arm = () => {
      const remaining = next - serverNow() + 1;
      timer =
        remaining > MAX_TIMEOUT_MS
          ? setTimeout(arm, MAX_TIMEOUT_MS)
          : setTimeout(() => setNow(new Date(serverNow())), remaining);
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
  const now = useNowAcross([start, freeze, end], info?.server_time);
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

/** Refetch the challenge list and details once the event starts. */
export function useRefetchChallengesOnStart(): void {
  const { upcoming } = useEventPhase();
  const queryClient = useQueryClient();
  const wasUpcoming = useRef(upcoming);

  useEffect(() => {
    if (wasUpcoming.current && !upcoming) {
      void queryClient.invalidateQueries({ queryKey: ["challenges"] });
      void queryClient.invalidateQueries({ queryKey: ["challenge"] });
    }
    wasUpcoming.current = upcoming;
  }, [upcoming, queryClient]);
}
