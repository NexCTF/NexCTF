import { Clock, Radio, Snowflake } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Banner } from "@/components/banner";
import { useEventPhase } from "@/lib/use-event-phase";

const MEDALS: Record<number, string> = {
  1: "bg-yellow-400/20 text-yellow-500",
  2: "bg-zinc-300/20 text-zinc-400",
  3: "bg-amber-700/20 text-amber-600",
};

export function RankBadge({ rank }: { rank: number }) {
  const medal = MEDALS[rank];
  return (
    <span
      className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm ${
        medal ? `${medal} font-bold` : "text-muted-foreground"
      }`}
    >
      {rank}
    </span>
  );
}

/** Competition not-started / running / frozen / ended notices. */
export function ScoreboardBanners() {
  const { t } = useTranslation();
  const { start, freeze, end, upcoming, running, frozen, ended } = useEventPhase();

  if (upcoming) {
    return (
      <Banner tone="yellow" icon={Clock}>
        {t("scoreboard.not_started_banner", { date: start?.toLocaleString() })}
      </Banner>
    );
  }
  if (!running && !ended && !frozen) return null;

  const runningLabel = end
    ? t("scoreboard.running_until_banner", {
        date: end.toLocaleString(),
        defaultValue: "Competition running, ends on {{date}}",
      })
    : t("scoreboard.running_banner", { defaultValue: "Competition running" });

  return (
    <div className="space-y-2">
      {running && (
        <Banner tone="green" icon={Radio}>
          {runningLabel}
        </Banner>
      )}
      {ended && (
        <Banner tone="zinc" icon={Clock}>
          {t("scoreboard.ended_banner", { date: end?.toLocaleString() })}
        </Banner>
      )}
      {frozen && (
        <Banner tone="blue" icon={Snowflake}>
          {t("scoreboard.frozen_banner", { date: freeze?.toLocaleString() })}
        </Banner>
      )}
    </div>
  );
}
