import { useQuery } from "@tanstack/react-query";
import { getPublicInfo } from "@/lib/api";

export interface EventPhase {
  start: Date | null;
  freeze: Date | null;
  end: Date | null;
  upcoming: boolean;
  running: boolean;
  frozen: boolean;
  ended: boolean;
}

function toDate(iso: string | undefined): Date | null {
  return iso ? new Date(iso) : null;
}

/** Event times from the public info and where *now* falls among them. */
export function useEventPhase(): EventPhase {
  const { data: info } = useQuery({
    queryKey: ["info", "public"],
    queryFn: getPublicInfo,
    staleTime: 60_000,
  });
  const now = new Date();
  const start = toDate(info?.competition.start_time);
  const freeze = toDate(info?.competition.freeze_time);
  const end = toDate(info?.competition.end_time);
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
  };
}

export function useEventEnded(): boolean {
  return useEventPhase().ended;
}
