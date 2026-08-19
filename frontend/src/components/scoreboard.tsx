import { useQuery } from "@tanstack/react-query";
import { Clock, Snowflake } from "lucide-react";
import { useTranslation } from "react-i18next";
import { getPublicInfo } from "@/lib/api";

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

/** Competition not-started / frozen / ended notices. */
export function ScoreboardBanners() {
  const { t } = useTranslation();
  const { data: publicInfo } = useQuery({
    queryKey: ["info", "public"],
    queryFn: getPublicInfo,
  });

  const now = new Date();
  const competition = publicInfo?.competition;
  const startTime = competition?.start_time ? new Date(competition.start_time) : null;
  const endTime = competition?.end_time ? new Date(competition.end_time) : null;
  const freezeTime = competition?.freeze_time ? new Date(competition.freeze_time) : null;

  const isEnded = endTime !== null && now > endTime;

  if (startTime !== null && now < startTime) {
    return (
      <Banner tone="yellow" icon={Clock}>
        {t("scoreboard.not_started_banner", { date: startTime.toLocaleString() })}
      </Banner>
    );
  }
  if (isEnded) {
    return (
      <Banner tone="zinc" icon={Clock}>
        {t("scoreboard.ended_banner", { date: endTime?.toLocaleString() })}
      </Banner>
    );
  }
  if (freezeTime !== null && now >= freezeTime) {
    return (
      <Banner tone="blue" icon={Snowflake}>
        {t("scoreboard.frozen_banner", { date: freezeTime.toLocaleString() })}
      </Banner>
    );
  }
  return null;
}

const TONES = {
  yellow: "border-yellow-500/30 bg-yellow-500/10 text-yellow-400",
  zinc: "border-zinc-500/30 bg-zinc-500/10 text-zinc-400",
  blue: "border-blue-500/30 bg-blue-500/10 text-blue-400",
};

function Banner({
  tone,
  icon: Icon,
  children,
}: {
  tone: keyof typeof TONES;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <div className={`flex items-center gap-2 rounded-lg border px-4 py-3 text-sm ${TONES[tone]}`}>
      <Icon className="h-4 w-4 shrink-0" />
      <span>{children}</span>
    </div>
  );
}
