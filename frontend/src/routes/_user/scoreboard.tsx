import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ChevronRight, Trophy } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BracketSelect } from "@/components/bracket-select";
import { RankBadge, ScoreboardBanners } from "@/components/scoreboard";
import {
  getScoreboard,
  getScoreboardHistory,
  type Scoreboard,
  type ScoreboardEntry,
  type TeamScoreSeries,
} from "@/lib/api";

export const Route = createFileRoute("/_user/scoreboard")({
  component: ScoreboardPage,
});

// 10-color palette for the chart lines
const TEAM_COLORS = [
  "#6366f1", // indigo
  "#ec4899", // pink
  "#f59e0b", // amber
  "#10b981", // emerald
  "#3b82f6", // blue
  "#ef4444", // red
  "#8b5cf6", // violet
  "#14b8a6", // teal
  "#f97316", // orange
  "#84cc16", // lime
];

function ScoreboardRow({
  entry,
  showBracket,
  fields,
  onOpen,
}: {
  entry: ScoreboardEntry;
  showBracket: boolean;
  fields: Scoreboard["custom_fields"];
  onOpen: (teamId: string) => void;
}) {
  return (
    <tr
      className="group transition-colors cursor-pointer hover:bg-accent/60 border-l-2 border-l-transparent hover:border-l-primary"
      onClick={() => onOpen(entry.team_id)}
    >
      <td className="px-4 py-3">
        <RankBadge rank={entry.rank} />
      </td>
      <td className="px-4 py-3 font-medium">{entry.team_name}</td>
      {showBracket && (
        <td className="px-4 py-3 text-muted-foreground capitalize">{entry.team_bracket ?? "—"}</td>
      )}
      {fields.map((f) => (
        <td key={f.name} className="px-4 py-3 text-muted-foreground">
          {entry.custom_fields[f.name] ?? "—"}
        </td>
      ))}
      <td className="px-4 py-3 text-right font-semibold tabular-nums">{entry.total}</td>
      <td className="px-3 py-3 w-8 text-muted-foreground/30 group-hover:text-primary transition-colors">
        <ChevronRight className="size-4 transition-transform group-hover:translate-x-0.5" />
      </td>
    </tr>
  );
}

/**
 * Merge all team series into a single array of chart data points.
 * Each point has a `ts` key (epoch ms) and one key per team.
 * Uses step-function logic: each team's score is carried forward until the
 * next event.
 */
function buildChartData(series: TeamScoreSeries[]) {
  if (series.length === 0) return [];

  // Collect all unique timestamps across all teams
  const allTs = new Set<number>();
  for (const s of series) {
    for (const ev of s.events) {
      allTs.add(new Date(ev.ts).getTime());
    }
  }
  const sortedTs = Array.from(allTs).sort((a, b) => a - b);

  // For each timestamp, compute cumulative score for every team at that point
  const latestScore: Record<string, number> = {};
  const teamEventIdx: Record<string, number> = {};
  for (const s of series) {
    latestScore[s.team_id] = 0;
    teamEventIdx[s.team_id] = 0;
  }

  return sortedTs.map((ts) => {
    // Advance each team's cursor to consume all events <= ts
    for (const s of series) {
      while (
        teamEventIdx[s.team_id] < s.events.length &&
        new Date(s.events[teamEventIdx[s.team_id]].ts).getTime() <= ts
      ) {
        latestScore[s.team_id] = s.events[teamEventIdx[s.team_id]].cumulative;
        teamEventIdx[s.team_id]++;
      }
    }

    const point: Record<string, number> = { ts };
    for (const s of series) {
      point[s.team_id] = latestScore[s.team_id];
    }
    return point;
  });
}

function ScoreEvolutionChart({ series }: { series: TeamScoreSeries[] }) {
  const { t } = useTranslation();
  const data = buildChartData(series);

  if (data.length === 0) {
    return (
      <p className="text-center text-muted-foreground py-8">{t("scoreboard.chart_no_data")}</p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
        <XAxis
          dataKey="ts"
          type="number"
          domain={["dataMin", "dataMax"]}
          scale="time"
          tickFormatter={(v: number) =>
            new Date(v).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })
          }
          tick={{ fontSize: 11 }}
          className="text-muted-foreground"
        />
        <YAxis tick={{ fontSize: 11 }} width={48} className="text-muted-foreground" />
        <Tooltip
          labelFormatter={(v) => new Date(v as number).toLocaleString()}
          formatter={(value, name) => {
            const team = series.find((s) => s.team_id === (name as string));
            return [value, team?.team_name ?? String(name)];
          }}
          contentStyle={{
            fontSize: "0.75rem",
            borderRadius: "0.5rem",
          }}
        />
        <Legend
          formatter={(value: string) => {
            const team = series.find((s) => s.team_id === value);
            return team?.team_name ?? value;
          }}
          wrapperStyle={{ fontSize: "0.75rem" }}
        />
        {series.map((s, i) => (
          <Line
            key={s.team_id}
            type="stepAfter"
            dataKey={s.team_id}
            stroke={TEAM_COLORS[i % TEAM_COLORS.length]}
            dot={false}
            strokeWidth={2}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function ScoreboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [bracket, setBracket] = useState<string | undefined>(undefined);

  const { data, isLoading, error } = useQuery({
    queryKey: ["scoreboard", bracket],
    queryFn: () => getScoreboard(bracket),
    refetchInterval: 30_000,
  });

  const { data: historyData } = useQuery({
    queryKey: ["scoreboard", "history", bracket],
    queryFn: () => getScoreboardHistory(10, bracket),
    refetchInterval: 30_000,
  });

  return (
    <div className="mx-auto max-w-screen-lg px-4 py-10 space-y-8">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Trophy className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-bold">{t("scoreboard.title")}</h1>
        </div>

        {data && <BracketSelect brackets={data.brackets} value={bracket} onChange={setBracket} />}
      </div>

      <ScoreboardBanners />

      {isLoading && <p className="text-muted-foreground">{t("common.loading")}</p>}

      {error && <p className="text-destructive">{t("scoreboard.load_error")}</p>}

      {historyData?.series.some((s) => s.events.length > 0) && (
        <div className="rounded-lg border p-4 space-y-3">
          <h2 className="text-base font-semibold">{t("scoreboard.chart_title")}</h2>
          <ScoreEvolutionChart series={historyData.series} />
        </div>
      )}

      {data && (
        <>
          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/40">
                <tr>
                  <th className="px-4 py-2.5 text-left text-muted-foreground font-medium w-12">
                    {t("scoreboard.col_rank")}
                  </th>
                  <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                    {t("scoreboard.col_team")}
                  </th>
                  {data.brackets.length > 0 && (
                    <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                      {t("scoreboard.bracket_label")}
                    </th>
                  )}
                  {data.custom_fields.map((f) => (
                    <th
                      key={f.name}
                      className="px-4 py-2.5 text-left text-muted-foreground font-medium"
                    >
                      {f.label}
                    </th>
                  ))}
                  <th className="px-4 py-2.5 text-right text-muted-foreground font-medium">
                    {t("scoreboard.col_total")}
                  </th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.entries.length === 0 ? (
                  <tr>
                    <td
                      colSpan={4 + (data.brackets.length > 0 ? 1 : 0) + data.custom_fields.length}
                      className="px-4 py-8 text-center text-muted-foreground"
                    >
                      {t("scoreboard.empty")}
                    </td>
                  </tr>
                ) : (
                  data.entries.map((entry) => (
                    <ScoreboardRow
                      key={entry.team_id}
                      entry={entry}
                      showBracket={data.brackets.length > 0}
                      fields={data.custom_fields}
                      onOpen={(teamId) =>
                        void navigate({ to: "/teams/$teamId", params: { teamId } })
                      }
                    />
                  ))
                )}
              </tbody>
            </table>
          </div>

          <p className="text-xs text-muted-foreground text-right">
            {t("scoreboard.computed_at", {
              date: new Date(data.computed_at).toLocaleString(),
            })}
          </p>
        </>
      )}
    </div>
  );
}
