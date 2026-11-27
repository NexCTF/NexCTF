import { useQuery } from "@tanstack/react-query";
import { Megaphone } from "lucide-react";
import { useCycle } from "@/hooks/use-cycle";
import { getMyNotifications } from "@/lib/api";
import { recentBroadcasts } from "@/lib/display";
import { serverNow } from "@/lib/server-clock";

/** How often the ticker looks for a new broadcast. */
const POLL_MS = 30_000;
/** How long each broadcast stays on screen. */
const CYCLE_MS = 8_000;

/** Bottom strip cycling through recent broadcasts; team notifications are never shown. */
export function DisplayTicker({ token }: { token: string | null }) {
  const { data } = useQuery({
    queryKey: ["display", "notifications", token],
    queryFn: () => getMyNotifications(token),
    refetchInterval: POLL_MS,
  });
  const recent = recentBroadcasts(data?.notifications ?? [], serverNow());
  const index = useCycle(recent.length, CYCLE_MS);
  const current = recent[index];
  if (!current) return null;

  return (
    <footer className="flex items-center gap-5 border-t bg-muted/40 px-10 py-4 text-2xl">
      <Megaphone className="size-8 shrink-0 text-primary" />
      <div
        key={current.id}
        className="flex min-w-0 flex-1 items-center gap-5 animate-in fade-in duration-700"
      >
        <span className="shrink-0 font-semibold">{current.title}</span>
        <span className="truncate text-muted-foreground">{current.content}</span>
      </div>
      {recent.length > 1 && (
        <span className="shrink-0 text-lg tabular-nums text-muted-foreground">
          {index + 1}/{recent.length}
        </span>
      )}
    </footer>
  );
}
