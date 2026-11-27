import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Trophy } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { BracketSelect } from "@/components/bracket-select";
import { CLICKABLE_ROW_CLS, RowChevron } from "@/components/data-table";
import { ScoreEvolutionChart } from "@/components/score-evolution-chart";
import { RankBadge, ScoreboardBanners } from "@/components/scoreboard";
import {
  getScoreboard,
  getScoreboardHistory,
  type Scoreboard,
  type ScoreboardEntry,
} from "@/lib/api";

export const Route = createFileRoute("/_user/scoreboard")({
  component: ScoreboardPage,
});

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
    <tr className={CLICKABLE_ROW_CLS} onClick={() => onOpen(entry.team_id)}>
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
      <RowChevron />
    </tr>
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
          <div className="rounded-lg border overflow-x-auto">
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
