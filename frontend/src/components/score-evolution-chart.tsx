import { memo, useMemo } from "react";
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
import type { TeamScoreSeries } from "@/lib/api";
import { cn } from "@/lib/utils";

// 10-color palette for the chart lines
export const TEAM_COLORS = [
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

/**
 * Merge all team series into a single array of chart data points.
 * Each point has a `ts` key (epoch ms) and one key per team.
 * Uses step-function logic: each team's score is carried forward until the
 * next event.
 */
export function buildChartData(series: TeamScoreSeries[]) {
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

interface ScoreEvolutionChartProps {
  series: TeamScoreSeries[];
  /** Chart height in pixels, or a CSS length such as "100%". */
  height?: number | `${number}%`;
  /** Font size of the axis ticks and legend, in pixels. */
  fontSize?: number;
  /** Width of a line, in pixels. */
  strokeWidth?: number;
  /** Classes of the message shown when no team has scored yet. */
  emptyClassName?: string;
}

/** Step chart of the cumulative score of each team over time. */
export const ScoreEvolutionChart = memo(function ScoreEvolutionChart({
  series,
  height = 320,
  fontSize = 11,
  strokeWidth = 2,
  emptyClassName,
}: ScoreEvolutionChartProps) {
  const { t } = useTranslation();
  const data = useMemo(() => buildChartData(series), [series]);

  if (data.length === 0) {
    return (
      <p className={cn("text-center text-muted-foreground py-8", emptyClassName)}>
        {t("scoreboard.chart_no_data")}
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
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
          tick={{ fontSize }}
          className="text-muted-foreground"
        />
        <YAxis
          tick={{ fontSize }}
          width={Math.max(48, fontSize * 4)}
          className="text-muted-foreground"
        />
        <Tooltip
          labelFormatter={(v) => new Date(v as number).toLocaleString()}
          formatter={(value, name) => {
            const team = series.find((s) => s.team_id === (name as string));
            return [value, team?.team_name ?? String(name)];
          }}
          contentStyle={{
            fontSize: "0.75rem",
            borderRadius: "0.5rem",
            backgroundColor: "var(--popover)",
            border: "1px solid var(--border)",
            color: "var(--popover-foreground)",
          }}
        />
        <Legend
          formatter={(value: string) => {
            const team = series.find((s) => s.team_id === value);
            return team?.team_name ?? value;
          }}
          wrapperStyle={{ fontSize: fontSize + 1 }}
        />
        {series.map((s, i) => (
          <Line
            key={s.team_id}
            type="stepAfter"
            dataKey={s.team_id}
            stroke={TEAM_COLORS[i % TEAM_COLORS.length]}
            dot={false}
            strokeWidth={strokeWidth}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
});
