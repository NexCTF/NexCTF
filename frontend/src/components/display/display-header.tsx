import { useQuery } from "@tanstack/react-query";
import { Clock, Flag, Radio, Snowflake, WifiOff } from "lucide-react";
import { type ElementType, type ReactNode, type RefObject, useState } from "react";
import { useTranslation } from "react-i18next";
import { TONES } from "@/components/banner";
import { useNow } from "@/hooks/use-now";
import { getPublicInfo } from "@/lib/api";
import { useBranding } from "@/lib/branding";
import { formatCountdown } from "@/lib/display";
import { serverNow } from "@/lib/server-clock";
import { useEventPhase } from "@/lib/use-event-phase";
import { cn } from "@/lib/utils";

/** Time without a successful refresh after which the screen says it is stale. */
export const STALE_AFTER_MS = 60_000;

function DisplayPill({
  tone,
  icon: Icon,
  children,
}: {
  tone: keyof typeof TONES;
  icon: ElementType;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "flex items-center gap-2 rounded-full border px-4 py-1.5 text-xl font-medium whitespace-nowrap",
        TONES[tone],
      )}
    >
      <Icon className="size-5" />
      {children}
    </span>
  );
}

interface EventStatus {
  tone: keyof typeof TONES;
  icon: ElementType;
  label: string;
}

/** Where the event stands: not started, live, frozen or finished. */
export function EventStatusBadge() {
  const { t } = useTranslation();
  const { upcoming, running, frozen, ended } = useEventPhase();

  let status: EventStatus | null = null;
  if (upcoming) {
    status = {
      tone: "yellow",
      icon: Clock,
      label: t("display.status_upcoming", { defaultValue: "Not started" }),
    };
  } else if (ended) {
    status = {
      tone: "zinc",
      icon: Flag,
      label: t("display.status_finished", { defaultValue: "Finished" }),
    };
  } else if (frozen) {
    status = {
      tone: "blue",
      icon: Snowflake,
      label: t("display.frozen", { defaultValue: "Scoreboard frozen" }),
    };
  } else if (running) {
    status = { tone: "green", icon: Radio, label: t("display.live", { defaultValue: "Live" }) };
  }
  if (!status) return null;

  return (
    <DisplayPill tone={status.tone} icon={status.icon}>
      {status.label}
    </DisplayPill>
  );
}

/**
 * Time of the last successful refresh, shown once it is older than STALE_AFTER_MS
 * (counted from mount while there has been none yet), or while part of the screen is
 * *failing* to load.
 */
export function StaleBadge({
  lastSuccess,
  failing = false,
}: {
  lastSuccess: RefObject<number | null>;
  failing?: boolean;
}) {
  const { t } = useTranslation();
  const [mountedAt] = useState(Date.now);
  const now = useNow(5000);
  const last = lastSuccess.current;
  if (!failing && now - (last ?? mountedAt) <= STALE_AFTER_MS) return null;

  const time = last ? new Date(last).toLocaleTimeString() : "—";
  return (
    <DisplayPill tone="amber" icon={WifiOff}>
      {t("display.stale", { time, defaultValue: "Last update {{time}}" })}
    </DisplayPill>
  );
}

/** Countdown to the start or the end of the event, ticking every second. */
function Countdown() {
  const { t } = useTranslation();
  const { start, end, upcoming, ended } = useEventPhase();
  const now = useNow(1000, serverNow);

  const target = upcoming ? start : ended ? null : end;
  if (!target) return null;
  const label = upcoming
    ? t("display.starts_in", { defaultValue: "Starts in" })
    : t("display.ends_in", { defaultValue: "Ends in" });

  return (
    <div className="text-right leading-tight">
      <div className="text-lg uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="font-mono text-5xl font-bold tabular-nums">
        {formatCountdown(target.getTime() - now, t("display.day_unit", { defaultValue: "d" }))}
      </div>
    </div>
  );
}

/** Logo (dark variant first) or event name, bracket on screen, status, freshness, countdown. */
export function DisplayHeader({
  bracket,
  lastSuccess,
  failing,
}: {
  bracket: string | undefined;
  /** Time of the last successful refresh; null hides the stale badge. */
  lastSuccess: RefObject<number | null> | null;
  /** Whether part of the screen, such as the chart, keeps failing to load. */
  failing: boolean;
}) {
  const { t } = useTranslation();
  const { name } = useBranding();
  const { data: info } = useQuery({
    queryKey: ["info", "public"],
    queryFn: getPublicInfo,
    staleTime: 5 * 60 * 1000,
  });
  const logo = info?.branding.logo_url_dark || info?.branding.logo_url;

  return (
    <header className="flex items-center justify-between gap-8 border-b px-10 py-5">
      <div className="flex min-w-0 items-center gap-6">
        {logo ? (
          <img src={logo} alt={name} className="h-16 max-w-96 object-contain" />
        ) : (
          <h1 className="truncate text-4xl font-bold tracking-tight">{name}</h1>
        )}
        {bracket && (
          <span className="rounded-full border px-4 py-1.5 text-xl capitalize text-muted-foreground">
            {t("display.bracket", { bracket, defaultValue: "Bracket: {{bracket}}" })}
          </span>
        )}
      </div>
      <div className="flex items-center gap-4">
        {lastSuccess && <StaleBadge lastSuccess={lastSuccess} failing={failing} />}
        <EventStatusBadge />
        <div className="ml-4">
          <Countdown />
        </div>
      </div>
    </header>
  );
}
